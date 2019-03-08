"""Interface to a Koji build service."""
import logging
import os
import time
from datetime import datetime
from datetime import timezone
from itertools import groupby
from itertools import starmap
from operator import attrgetter
from operator import itemgetter
from pathlib import Path
from typing import AbstractSet
from typing import Any
from typing import Iterator
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING

import attr
import requests
from attr.validators import instance_of
from attr.validators import optional
from click import style

from . import abc
from .. import rpm
from ..configuration import service
from ..util import system_import

if TYPE_CHECKING:
    import koji
else:
    koji = system_import("koji")

logger = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True, cmp=False)
class BuiltPackage(rpm.Metadata):
    """Data for a built RPM package presented by a Koji service.

    This class serves as an adaptor between build data provided as
    raw dictionaries by the build server, and the rpm.Metadata interface.
    """

    #: Unique identification of a build within the service
    id = attr.ib(validator=instance_of(int), converter=int, default=None)

    @classmethod
    def from_mapping(cls, raw_data: Mapping) -> "BuiltPackage":
        """Explicitly create BuiltPackage from mapping that contain extra keys.

        This constructor accepts any existing mapping and cherry-picks
        only the valid attribute keys. Any extra data are ignored and
        discarded.

        Keyword arguments:
            raw_data: The mapping that should be used for the initialization.

        Returns:
            New BuiltPackage instance.
        """

        valid_keys = {attribute.name for attribute in attr.fields(cls)}
        known_data = {
            key: value for key, value in raw_data.items() if key in valid_keys
        }

        return cls(**known_data)

    @classmethod
    def from_metadata(
        cls, service: "Service", original: rpm.Metadata
    ) -> "BuiltPackage":
        """'Downcast' a Metadata instance by downloading missing data.

        Keyword arguments:
            service: The service to use for fetching missing data.
            original: The original rpm.Metadata to get additional
                data for.

        Returns:
            New BuiltPackage instance for the original metadata.
        """

        if isinstance(original, cls):  # already downcasted
            return original

        raw_data = service.session.getBuild(attr.asdict(original))
        return cls.from_mapping(raw_data)


@service.register("koji", initializer="from_config_profile")
@attr.s(slots=True, frozen=True)
class Service(abc.Repository, abc.Builder):
    """Interaction session with a Koji build service."""

    #: Client configuration for this service
    configuration: Mapping[str, Any] = attr.ib(validator=instance_of(Mapping))

    #: XMLRPC session for communication with the service
    session: koji.ClientSession = attr.ib(validator=instance_of(koji.ClientSession))

    #: Information about remote URLs and paths
    path_info: koji.PathInfo = attr.ib(validator=instance_of(koji.PathInfo))

    #: Tag prefixes associated with this Koji instance
    tag_prefixes: AbstractSet = attr.ib(
        validator=instance_of(AbstractSet), converter=set, default=attr.Factory(set)
    )

    #: Target prefixes associated with this koji instance
    target_prefixes: AbstractSet = attr.ib(
        validator=instance_of(AbstractSet), converter=set, default=attr.Factory(set)
    )

    #: Owner to use when adding packages to tag
    default_owner: Optional[str] = attr.ib(  # noqa: E704
        validator=optional(instance_of(str)), default=None
    )

    # Dynamic defaults

    @session.default
    def configured_session(self):
        """ClientSession from configuration values."""
        return koji.ClientSession(self.configuration["server"])

    @path_info.default
    def configured_path_info(self):
        """PathInfo from configuration values."""
        return koji.PathInfo(self.configuration["topurl"])

    # Alternate constructors

    @classmethod
    def from_config_profile(cls, profile_name: str, **kwargs) -> "Service":
        """Constructs new instance from local configuration profile.

        Keyword arguments:
            profile_name: Name of the profile to use.
        """

        return cls(configuration=koji.read_config(profile_name), **kwargs)

    # Session authentication

    def __enter__(self) -> "Service":
        """Authenticate to the service using SSL certificates."""

        credentials = {
            kind: os.path.expanduser(self.configuration[kind])
            for kind in ("cert", "ca", "serverca")
        }

        self.session.ssl_login(**credentials)

        return self

    def __exit__(self, *exc_info) -> bool:
        """Log out from the service."""

        self.session.logout()

        return False  # do not suppress the exception

    # Queries

    def latest_builds(self, tag_name: str) -> Iterator[BuiltPackage]:
        """List latest builds within a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.

        Yields:
            Metadata for the latest builds in the specified tag.
        """

        build_list = self.session.listTagged(tag_name)
        build_iter = map(BuiltPackage.from_mapping, build_list)
        build_groups = groupby(sorted(build_iter), key=attrgetter("name"))
        latest_iter = starmap(lambda _name, group: max(group), build_groups)

        yield from latest_iter

    def tag_entry_time(self, tag_name: str, build: rpm.Metadata) -> Optional[datetime]:
        """Determine the entry time of a build into a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.
            build: The metadata of the build in question.

        Returns:
            The date and time the build entered into the tag.
            If the build is not present within the tag, returns None.
        """

        # Ensure the build has an ID
        build = BuiltPackage.from_metadata(self, build)

        # Fetch tag history for this build, and extract latest entry time
        history = self.session.tagHistory(tag=tag_name, build=build.id)
        timestamp = max(map(itemgetter("create_ts"), history), default=None)

        if timestamp is None:
            return None
        else:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    # Tasks

    def download(
        self,
        package: rpm.Metadata,
        target_dir: Path,
        *,
        session: Optional[requests.Session] = None,
    ) -> rpm.LocalPackage:
        """Download a single package from the service.

        Keyword arguments:
            package: The metadata for the package to download.
            target_dir: Path to existing directory to store the
                downloaded package to.
            session: Optional requests Session to use.

        Returns:
            Path to the downloaded package.

        Raises:
            requests.HTTPError: On HTTP errors.
        """

        if session is None:
            # Re-use the internal ClientSession requests Session
            session = self.session.rsession

        # The build ID is needed
        if isinstance(package, BuiltPackage):
            build = package
        else:
            build = BuiltPackage.from_metadata(self, package)

        rpm_list = self.session.listRPMs(buildID=build.id, arches=build.arch)
        # Get only the package exactly matching the metadata
        candidate_list = map(BuiltPackage.from_mapping, rpm_list)

        target_pkg, = (c for c in candidate_list if c.nevra == build.nevra)
        target_url = "/".join(
            [
                self.path_info.build(attr.asdict(build)),
                self.path_info.rpm(attr.asdict(target_pkg)),
            ]
        )

        target_file_path = target_dir / target_url.rsplit("/")[-1]

        response = session.get(target_url, stream=True)
        response.raise_for_status()

        with target_file_path.open(mode="wb") as ostream:
            for chunk in response.iter_content(chunk_size=256):
                ostream.write(chunk)

        return rpm.LocalPackage(target_file_path)

    def tag_build(
        self,
        tag_name: str,
        build_metadata: rpm.Metadata,
        *,
        owner: Optional[str] = None,
    ) -> rpm.Metadata:
        """Add an existing build to a new tag.

        Keyword arguments:
            tag_name: Name of the tag to which the build should be added.
            build_metadata: Description of the build to tag.
            owner: The name of the owner of new package in the tag.

        Returns:
            Metadata of the tagged build.

        Raises:
            ValueError: tag_name does not name any tag handled by this
                instance.
            ValueError: build_metadata describes a build not existing
                within this instance.
        """

        # Ensure that the package is in the package list
        self.session.packageListAdd(
            tag_name,
            build_metadata.name,
            owner=owner if owner is not None else self.default_owner,
        )

        # Create the task
        task_id = self.session.tagBuild(tag_name, build_metadata.nvr)

        # Wait for the task to finish
        self.__watch_task(task_id, silent=True, poll_interval=3)

        return build_metadata

    def __query_target(self, target_name: str) -> dict:
        """Queries the service for information on a target.

        Keyword arguments:
            target_name: The name of the target to query.

        Returns:
            A dictionary with provided target information.

        Raises:
            ValueError: The requested target is not known to the service.
        """

        info = self.session.getBuildTarget(target_name)

        if info is not None:
            return info
        else:
            message = (
                'Build target "{target_name}" ' "is not handled by this service."
            ).format(target_name=target_name)
            raise ValueError(message)

    def __upload_srpm(self, source_package: rpm.LocalPackage) -> str:
        """Upload a local SRPM to automatically determined remote directory.

        Keyword arguments:
            source_package: The SRPM to upload.

        Returns:
            Remote path to the uploaded package.
        """

        remote_dir = "{timestamp:%Y-%m-%dT%H:%M:%S}-{package.nevra}".format(
            timestamp=datetime.now(timezone.utc), package=source_package.metadata
        )

        logger.debug(
            "Uploading {package.path} to {remote_dir}".format(
                package=source_package, remote_dir=remote_dir
            )
        )
        self.session.uploadWrapper(source_package.path, remote_dir)

        return "/".join((remote_dir, source_package.path.name))

    def __queue_build(self, target: Mapping, remote_package_path: str) -> int:
        """Queue a build task of remote_package_path into target_name.

        Keyword arguments:
            target: The target information mapping.
            remote_package_path: The path to the SRPM to build.

        Returns:
            Numeric task ID for the queued build.
        """

        logger.debug(
            "Starting build of {remote_package} to {target[name]}".format(
                remote_package=remote_package_path.rpartition("/")[-1], target=target
            )
        )

        return self.session.build(remote_package_path, target["name"])

    def __watch_task(
        self,
        task_id: int,
        poll_interval: int,
        *,
        built_package: Optional[rpm.Metadata] = None,
        silent: bool = False,
    ) -> int:
        """Watch a task until its end.

        Keyword arguments:
            task_id: Numeric identification of the task to watch.
            poll_interval: Interval (in seconds) of task state queries.
            built_package: Metadata of the package being built
                (for more informative log messages).
            silent: If True, suppress logging output.

        Returns:
            A numeric identification of final task state (koji.TASK_STATES).
        """

        def name_state(task_info: Mapping) -> Optional[str]:
            """Extract the name of the state from the task info, if present."""

            state_number = task_info.get("state", None)
            return koji.TASK_STATES.get(state_number, None)

        def log_state(task_info: Mapping) -> None:
            """Log current task state."""

            if silent:
                return

            COLORS: Mapping[str, Mapping] = {
                "FREE": dict(fg="cyan"),
                "OPEN": dict(fg="yellow"),
                "CLOSED": dict(fg="green"),
                "CANCELED": dict(fg="yellow", bold=True),
                "ASSIGNED": dict(fg="magenta"),
                "FAILED": dict(fg="red", bold=True),
            }

            state_name = name_state(task_info) or "UNKNOWN"

            message = "Build task {id} [{nevra}]: {state_name}".format(
                id=task_info["id"],
                nevra=built_package.nevra if built_package else "unknown",
                state_name=state_name,
            )

            logger.info(style(message, **COLORS.get(state_name, {})))

        END_STATE_SET = {"CLOSED", "CANCELED", "FAILED"}

        task_info = self.session.getTaskInfo(task_id)
        log_state(task_info)

        # Wait until finished, log any detected state changes
        while name_state(task_info) not in END_STATE_SET:
            time.sleep(poll_interval)

            new_info = self.session.getTaskInfo(task_id)
            if new_info["state"] != task_info["state"]:
                log_state(new_info)

            task_info = new_info

        return task_info["state"]

    def build(
        self,
        target_name: str,
        source_package: rpm.LocalPackage,
        *,
        poll_interval: int = 5,
    ) -> BuiltPackage:
        """Build package using the service.

        Keyword arguments:
            target_name: Name of the target to build into.
            source_package: The package to build.
            poll_interval: Interval (in seconds) of querying the task state
                when watching.

        Returns:
            Metadata for a successfully built SRPM package.

        Raises:
            ValueError: Unknown target.
            BuildFailure: Build failure explanation.
        """

        target = self.__query_target(target_name)  # raises on unknown target
        remote_package = self.__upload_srpm(source_package)
        build_task_id = self.__queue_build(target, remote_package)
        result = self.__watch_task(
            build_task_id,
            poll_interval=poll_interval,
            built_package=source_package.metadata,
        )
        success = result == koji.TASK_STATES["CLOSED"]

        if not success:
            try:
                self.session.getTaskResult(build_task_id)  # always raise
            except koji.GenericError as original:  # extract the reason
                reason = original.args[0].partition(":")[0]  # up to first :
                raise abc.BuildFailure(source_package.metadata, reason) from None

        build_params = {
            key: getattr(source_package.metadata, key)
            for key in ("name", "version", "release", "epoch")
        }
        built_metadata = self.session.getBuild(build_params, strict=True)
        return BuiltPackage.from_mapping(built_metadata)
