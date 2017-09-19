"""Interface to a Koji build service."""

import os
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


@service.register('koji', initializer='from_config_profile')
@attr.s(slots=True, frozen=True)
class Service(abc.Repository):
    """Interaction session with a Koji build service."""

    #: Tag prefixes associated with this Koji instance
    tag_prefixes = attr.ib(validator=instance_of(Set), convert=set)

    #: Client configuration for this service
    configuration = attr.ib(validator=instance_of(Mapping))

    #: XMLRPC session for communication with the service
    session = attr.ib(validator=instance_of(koji.ClientSession), init=False)

    #: Information about remote URLs and paths
    path_info = attr.ib(validator=instance_of(koji.PathInfo), init=False)

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
