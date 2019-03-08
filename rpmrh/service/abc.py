"""Interface definitions for the service kinds."""
from abc import ABCMeta
from abc import abstractmethod
from contextlib import ContextDecorator
from datetime import datetime
from pathlib import Path
from typing import AbstractSet
from typing import Iterator
from typing import Optional

import attr
import requests
from attr.validators import instance_of

from .. import rpm
from ..exception import UserError


@attr.s(slots=True, frozen=True)
class Repository(metaclass=ABCMeta):
    """A service providing existing packages and their metadata.

    Besides defining the required interface, the main job of this class
    is to keep track which of its instances handles which tag.
    """

    # Required methods and properties
    @property
    @abstractmethod
    def tag_prefixes(self) -> AbstractSet[str]:
        """Set of tag prefixes associated with this Repository."""

    @abstractmethod
    def latest_builds(self, tag_name: str) -> Iterator[rpm.Metadata]:
        """Provide metadata for all latest builds within a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.

        Yields:
            Metadata for all latest builds within the tag.
        """

    def tag_entry_time(self, tag_name: str, build: rpm.Metadata) -> Optional[datetime]:
        """Determine the entry time of a build into a tag.

        Keyword arguments:
            tag_name: Name of the tag to query.
            build: The metadata of the build in question.

        Returns:
            The date and time the build entered into the tag.
            If the build is not present within the tag, returns None.

        Raises:
            NotImplementedError:
                Entry time query is not supported on this repository type.
        """

        message = "Tag entry time query unsupported by {class_name}"
        raise NotImplementedError(message.format(class_name=type(self).__name__))

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


@attr.s(slots=True, frozen=True)
class BuildFailure(UserError):
    """Indicate build failure."""

    lead = "Build failure"

    #: The package that failed to build
    package = attr.ib(validator=instance_of(rpm.Metadata))
    #: The reason why the build failed
    reason = attr.ib(validator=instance_of(str))

    def __attr_post_init__(self):
        """Initialize super-class"""

        super(BuildFailure, self).__init__(self.reason)

    def __str__(self):
        return "{s.package.nvr}: {s.reason}".format(s=self)

    def format_message(self):
        return str(self)


class Builder(ContextDecorator, metaclass=ABCMeta):
    """A service that can build a source package.

    Since building may require elevated privileges,
    this class also acts as a context manager (and decorator).
    Use __enter__ to elevate the privileges (i.e. login)
    and __exit__ to clean up afterwards (i.e. logout).
    """

    @property
    @abstractmethod
    def target_prefixes(self) -> AbstractSet[str]:
        """Set of target prefixes associated with this Builder."""

    @abstractmethod
    def build(self, target_name: str, source_package: rpm.LocalPackage) -> rpm.Metadata:
        """Build a source package using this Builder.

        Keyword arguments:
            target_name: The target to build into.
            source_package: The package to build.

        Returns:
            Metadata for the SRPM created by the builder from source_package.

        Raises:
            BuildFailure: On unsuccessful build.
        """

    # Default implementation for optional methods

    def __enter__(self):
        return self

    def __exit__(_self, *_exc_info):
        return None  # Exception not handled, continue propagation
