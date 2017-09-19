"""Interface definitions for the service kinds."""

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Set, Iterator, Optional

import attr
import requests

from .. import rpm


@attr.s(slots=True, frozen=True)
class Repository(metaclass=ABCMeta):
    """A service providing existing packages and their metadata.

    Besides defining the required interface, the main job of this class
    is to keep track which of its instances handles which tag.
    """

    # Required methods and properties
    @property
    @abstractmethod
    def tag_prefixes(self) -> Set[str]:
        """Set of tag prefixes associated with this Repository."""

    @abstractmethod
    def latest_builds(self, tag_name: str) -> Iterator[rpm.Metadata]:
        """Provide metadata for all latest builds within a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.

        Yields:
            Metadata for all latest builds within the tag.
        """

    @abstractmethod
    def download(
        self,
        package: rpm.Metadata,
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
