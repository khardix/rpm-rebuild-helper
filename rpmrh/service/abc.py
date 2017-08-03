"""Interface definitions for the service kinds."""

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import ClassVar, Set, Iterator, Optional

import attr
import requests
from attr.validators import instance_of
from pytrie import Trie, StringTrie

from .. import rpm


@attr.s(init=False, slots=True)
class Repository(metaclass=ABCMeta):
    """A service providing existing packages and their metadata.

    Besides defining the required interface, the main job of this class
    is to keep track which of its instances handles which tag.
    """

    #: Registry of known tag to its associated repository instance
    registry: ClassVar[Trie] = StringTrie()

    #: Set of tags associated with the instance
    tag_prefixes = attr.ib(validator=instance_of(Set[str]))

    def __init__(self, tag_prefixes: Set[str], **other):
        """Register tags for this instance.

        Keyword arguments:
            tag_prefixes: Set of tag prefixes associated with this instance.
        """

        self.tag_prefixes = tag_prefixes

        for prefix in self.tag_prefixes:
            Repository.registry[prefix] = self

        # Support cooperative multiple inheritance
        # Note: Since the class is decorated, need to be explicit here
        super(Repository, self).__init__(**other)

    # Required methods

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
    ) -> Path:
        """Download a single package from the Repository.

        Keyword arguments:
            package: Metadata identifying the package to download.
            target_dir: Directory to save the package into.
            session: requests session to use for downloading.

        Returns:
            Path to the downloaded package.
        """
