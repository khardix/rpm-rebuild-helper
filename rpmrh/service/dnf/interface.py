"""Interface to DNF repositories."""
from pathlib import Path
from typing import Iterable
from typing import Iterator
from typing import Mapping
from typing import Optional
from typing import Set
from typing import TYPE_CHECKING

import attr
import requests
from attr.validators import instance_of

from .. import abc
from ... import report
from ... import rpm
from ...configuration import service
from ...util import default_requests_session
from ...util import system_import
from ._compat import make_compatible

if TYPE_CHECKING:
    import dnf
else:
    dnf = system_import("dnf")


@report.serializable
@attr.s(slots=True, frozen=True)
class Package:
    """Package information provided by DNF.

    The original `dnf.package.Package` is not designed
    to be used without `dnf.base.Base` or `dnf.sack.Sack`.
    This class thus serves as alternative container for the provided information
    decoupled from the DNF internals.
    """

    metadata: rpm.Metadata = attr.ib()
    scl: Optional[rpm.SoftwareCollection] = attr.ib(default=None)

    @classmethod
    def from_internal_dnf_package(
        cls, original: dnf.package.Package, **extra
    ) -> "Package":
        """Convert internal DNF package structure to decoupled representation.

        Arguments:
            original: The internal DNF package to be converted.

        Keyword arguments: Extra values not extracted from original
            (i.e. ``scl``).

        Returns: Decoupled equivalent of the original.
        """

        metadata = rpm.Metadata(
            **{a.name: getattr(original, a.name) for a in attr.fields(rpm.Metadata)}
        )

        return cls(metadata=metadata, **extra)


@service.register("dnf", initializer="configured")
@attr.s(slots=True, frozen=True)
class RepoGroup(abc.Repository):
    """Group of managed DNF repositories."""

    #: dnf.Base object managing the group
    base = attr.ib(validator=instance_of(dnf.Base), converter=make_compatible)

    @classmethod
    def configured(cls, repo_configs: Iterable[Mapping]):
        """Create a new instance from repository configurations.

        Keyword arguments:
            repositories: Configuration values for each repository.

        Returns:
            Configured RepoGroup.
        """

        base = dnf.Base()

        for config in repo_configs:
            # Make independent shallow copy for our modification
            config = dict(config)
            # Convert arguments to proper API
            arguments = {
                "repoid": config.pop("name"),
                "conf": base.conf,
                "baseurl": [config.pop("baseurl")],
            }

            base.repos.add_new_repo(**arguments, **config)

        return cls(base)

    @property
    def tag_prefixes(self) -> Set[str]:
        """Present the repository IDs as the valid tag prefixes."""

        return self.base.repos.keys()

    def latest_builds(self, tag_name: str) -> Iterator[rpm.PackageLike]:
        """Provide metadata for all latest builds within a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.

        Yields:
            Metadata for all latest builds within the tag.
        """

        self.base.repos.all().disable()
        self.base.repos.get_matching(tag_name).enable()
        self.base.fill_sack(load_system_repo=False)

        query = self.base.sack.query()
        yield from map(Package.from_internal_dnf_package, query.latest())

    def download(
        self,
        package: rpm.PackageLike,
        target_dir: Path,
        *,
        session: Optional[requests.Session] = None
    ) -> rpm.LocalPackage:
        """Download a single package from the Repository.

        Keyword arguments:
            package: Metadata identifying the package to download.
            target_dir: Directory to save the package into.
            session: requests session to use for downloading.

        Returns:
            Path to the downloaded package.
        """

        session = default_requests_session(session)

        self.base.repos.all().enable()
        self.base.fill_sack(load_system_repo=False)

        query = self.base.sack.query()
        (candidate,) = query.filter(**attr.asdict(package.metadata))
        source_url = candidate.remote_location()

        response = session.get(source_url, stream=True)
        response.raise_for_status()

        target_path = target_dir / source_url.rsplit("/")[-1]
        with target_path.open(mode="wb") as ostream:
            for chunk in response.iter_content(chunk_size=256):
                ostream.write(chunk)

        return rpm.LocalPackage(target_path)
