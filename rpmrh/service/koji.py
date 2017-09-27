"""Interface to a Koji build service."""

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Optional, Set

import attr
import requests
from attr.validators import instance_of

from . import abc
from .. import rpm
from ..configuration import service
from ..util import system_import

koji = system_import('koji')

logger = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class BuiltPackage(rpm.Metadata):
    """Data for a built RPM package presented by a Koji service.

    This class serves as an adaptor between build data provided as
    raw dictionaries by the build server, and the rpm.Metadata interface.
    """

    #: Unique identification of a build within the service
    id = attr.ib(validator=instance_of(int), convert=int, default=None)

    @classmethod
    def from_mapping(cls, raw_data: Mapping) -> 'BuiltPackage':
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
            key: value
            for key, value in raw_data.items()
            if key in valid_keys
        }

        return cls(**known_data)

    @classmethod
    def from_metadata(
        cls,
        service: 'Service',
        original: rpm.Metadata
    ) -> 'BuiltPackage':
        """'Downcast' a Metadata instance by downloading missing data.

        Keyword arguments:
            service: The service to use for fetching missing data.
            original: The original rpm.Metadata to get additional
                data for.

        Returns:
            New BuiltPackage instance for the original metadata.
        """

        raw_data = service.session.getBuild(attr.asdict(original))
        return cls.from_mapping(raw_data)


@attr.s(slots=True, frozen=True)
class BuildFailure(Exception):
    """Report failed build."""

    # The package that failed to build
    package = attr.ib(validator=instance_of(rpm.Metadata))
    # The reason for failure
    reason = attr.ib(validator=instance_of(str))

    def __attr_post_init__(self):
        """Initialize superclass"""

        super().__init__(str(self))

    def __str__(self):
        return '{s.package!s}: {s.reason}'.format(s=self)


@service.register('koji', initializer='from_config_profile')
@attr.s(slots=True, frozen=True)
class Service(abc.Repository):
    """Interaction session with a Koji build service."""

    #: Client configuration for this service
    configuration = attr.ib(validator=instance_of(Mapping))

    #: XMLRPC session for communication with the service
    session = attr.ib(validator=instance_of(koji.ClientSession))

    #: Information about remote URLs and paths
    path_info = attr.ib(validator=instance_of(koji.PathInfo))

    #: Tag prefixes associated with this Koji instance
    tag_prefixes = attr.ib(
        validator=instance_of(Set),
        convert=set,
        default=attr.Factory(set),
    )

    #: Target prefixes associated with this koji instance
    target_prefixes = attr.ib(
        validator=instance_of(Set),
        convert=set,
        default=attr.Factory(set),
    )

    # Dynamic defaults

    @session.default
    def configured_session(self):
        """ClientSession from configuration values."""
        return koji.ClientSession(self.configuration['server'])

    @path_info.default
    def configured_path_info(self):
        """PathInfo from configuration values."""
        return koji.PathInfo(self.configuration['topurl'])

    # Alternate constructors

    @classmethod
    def from_config_profile(cls, profile_name: str, **kwargs) -> 'Service':
        """Constructs new instance from local configuration profile.

        Keyword arguments:
            profile_name: Name of the profile to use.
        """

        return cls(
            configuration=koji.read_config(profile_name),
            **kwargs,
        )

    # Session authentication

    def __enter__(self) -> 'Service':
        """Authenticate to the service using SSL certificates."""

        credentials = {
            kind: os.path.expanduser(self.configuration[kind])
            for kind in ('cert', 'ca', 'serverca')
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

        build_list = self.session.listTagged(tag_name, latest=True)
        yield from map(BuiltPackage.from_mapping, build_list)

    # Tasks

    def download(
        self,
        package: rpm.Metadata,
        target_dir: Path,
        *,
        session: Optional[requests.Session] = None
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
            build = BuiltPackage.from_metadata(package)

        rpm_list = self.session.listRPMs(buildID=build.id, arches=build.arch)
        # Get only the package exactly matching the metadata
        candidate_list = map(BuiltPackage.from_mapping, rpm_list)

        target_pkg, = (c for c in candidate_list if c.nevra == build.nevra)
        target_url = '/'.join([
            self.path_info.build(attr.asdict(build)),
            self.path_info.rpm(attr.asdict(target_pkg)),
        ])

        target_file_path = target_dir / target_url.rsplit('/')[-1]

        response = session.get(target_url, stream=True)
        response.raise_for_status()

        with target_file_path.open(mode='wb') as ostream:
            for chunk in response.iter_content(chunk_size=256):
                ostream.write(chunk)

        return rpm.LocalPackage.from_path(target_file_path)

    def build(
        self,
        target: str,
        source_package: rpm.LocalPackage,
        *,
        poll_interval: int = 5
    ) -> BuiltPackage:
        """Build package using the service.

        Keyword arguments:
            target: Name of the target to build into.
            source_package: The package to build.
            poll_interval: Interval (in seconds) of querying the task state
                when watching.

        Returns:
            Metadata for a successfully built SRPM package.

        Raises:
            BuildFailure: Build failure explanation.
        """

        pkg_label = str(source_package)

        # Upload the package
        remote_dir = '{timestamp:%Y-%m-%dT%H:%M:%S}-{package!s}'.format(
            timestamp=datetime.now(timezone.utc),
            package=source_package,
        )

        logger.debug('Uploading {pkg} to {remote}'.format(
            pkg=pkg_label,
            remote=remote_dir,
        ))

        self.session.uploadWrapper(source_package.path, remote_dir)
        remote_package = '/'.join((remote_dir, source_package.path.name))

        # Start the build
        target_info = self.session.getBuildTarget(target)
        if target_info is None:
            raise ValueError('Unknown build target: {}'.format(target))

        logger.debug('Staring build of {pkg}'.format(pkg=pkg_label))
        build_task_id = self.session.build(remote_package, target_info['name'])

        # Wait for the build to finish
        def state(task_info):
            """Extract state information from task"""

            key = task_info.get('state', None)
            return koji.TASK_STATES.get(key, None)

        def log_state(task_info, old_info={}):
            """Logs state of a task, if the state was changed"""

            if task_info['state'] == old_info.get('state', None):
                return

            logger.info('Build task {id} [{package}]: {state}'.format(
                id=task_info['id'],
                package=source_package,
                state=state(task_info),
            ))

        build_info = self.session.getTaskInfo(build_task_id)
        log_state(build_info)

        while state(build_info) not in {'CLOSED', 'CANCELED', 'FAILED'}:
            time.sleep(poll_interval)

            new_info = self.session.getTaskInfo(build_task_id)
            log_state(new_info, build_info)
            build_info = new_info

        log_state(build_info)  # report final state

        # Process the final build state
        if state(build_info) == 'CLOSED':  # Build successful
            return BuiltPackage.from_mapping(
                self.session.getBuild(attr.asdict(source_package))
            )
        else:
            try:  # Convert GenericError to BuildFailure
                self.session.getTaskResult(build_task_id)
            except koji.GenericError as original:
                # Take the message up to the first colon
                reason = original.args[0].split(':', 1)[0]
                raise BuildFailure(source_package, reason) from None
