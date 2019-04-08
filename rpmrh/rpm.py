"""RPM-related classes and procedures."""
import operator
import re
from functools import partialmethod
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import ClassVar
from typing import NewType
from typing import Optional
from typing import Tuple
from typing import Union

import attr
from attr.validators import instance_of
from ruamel import yaml
from typing_extensions import Protocol
from typing_extensions import runtime

from . import report
from .util import system_import

_rpm = system_import("rpm")

# type aliases and helpers
CompareOperator = Callable[[Any, Any], bool]


# Argument normalization
_DEFAULT_EPOCH: int = 0
_DEFAULT_ARCH: str = "src"


def _normalize_epoch(epoch: Union[str, bytes, int, None]) -> int:
    """Normalize epoch value into proper integer."""

    return int(epoch) if epoch is not None else _DEFAULT_EPOCH


def _normalize_architecture(architecture: Union[str, None]) -> str:
    """Normalize architecture value into string."""

    return architecture if architecture is not None else _DEFAULT_ARCH


def _normalize_path(path: Union[str, Path]) -> Path:
    """Normalize path arguments into canonical absolute paths"""

    return Path(path).resolve()


@attr.s(slots=True, cmp=False, frozen=True, hash=True)
class Metadata:
    """Generic RPM metadata.

    This class should act as a basis for all the RPM-like objects,
    providing common comparison and other "dunder" methods.
    """

    @attr.s(frozen=True, slots=True)
    class DistTag:
        """Rich(er) representation of the distribution tag information."""

        #: Regular expression for finding and retrieving the tag from release
        _RE: ClassVar = re.compile(
            r"""\.              # short dist tag starts with a dot…
            (?P<id>[^\W\d_]+)   # … followed by at least one letter…
            (?P<major>\d+)      # … and ended by at least one digit
            (?P<trail>[^.]*)    # any other characters up to the next dot
        """,
            flags=re.VERBOSE,
        )

        #: Distribution identifier (i.e. ``el``)
        identifier: str = attr.ib()
        #: Major distribution version
        major: int = attr.ib(converter=int)
        #: Trailing information from the dist tag
        trailing: str = attr.ib(default="")

        @classmethod
        def from_release(cls, release_string: str) -> "Metadata.DistTag":
            """Attempt to parse distribution tag from release_string.

            Arguments:
                release_string: The release string to search in.

            Returns:
                Parsed DistTag.

            Raises:
                ValueError: No distribution tag found in release_string.
            """

            match = cls._RE.search(release_string)
            if match is None:
                message = "No distribution tag found in release string"
                raise ValueError(message, release_string)

            return cls(
                identifier=match.group("id"),
                major=match.group("major"),
                trailing=match.group("trail"),
            )

        def __str__(self) -> str:
            return "".join(map(str, attr.astuple(self)))

    #: Regular expression for extracting epoch from an NEVRA string
    _EPOCH_RE: ClassVar = re.compile(r"(\d+):")
    #: Regular expression for splitting up NVR string
    _NVRA_RE: ClassVar = re.compile(
        r"""
        ^
        (?P<name>\S+)-          # package name
        (?P<version>[\w.]+)-    # package version
        (?P<release>\w+(?:\.[\w+]+)+?)  # package release, with required dist tag
        (?:\.(?P<arch>\w+))?    # optional package architecture
        (?:\.rpm)?              # optional rpm extension
        $
        """,
        flags=re.VERBOSE,
    )

    # .el7_4 format

    #: RPM name
    name: str = attr.ib(validator=instance_of(str))
    #: RPM version
    version: str = attr.ib(validator=instance_of(str))
    #: RPM release
    release: str = attr.ib(validator=instance_of(str))

    #: Optional RPM epoch
    epoch: int = attr.ib(
        validator=instance_of(int), default=_DEFAULT_EPOCH, converter=_normalize_epoch
    )

    #: RPM architecture
    arch: str = attr.ib(
        validator=instance_of(str),
        default=_DEFAULT_ARCH,
        converter=_normalize_architecture,
    )

    # Alternative constructors

    @classmethod
    def from_nevra(cls, nevra: str) -> "Metadata":
        """Parse a string NEVRA and converts it to respective fields.

        Keyword arguments:
            nevra: The name-epoch:version-release-arch to parse.

        Returns:
            New instance of Metadata.

        Raises:
            ValueError: The :ref:`nevra` argument is not valid NEVRA string.
        """

        arguments = {}

        # Extract the epoch, if present
        def replace_epoch(match):
            arguments["epoch"] = match.group(1)
            return ""

        nvra = cls._EPOCH_RE.sub(replace_epoch, nevra, count=1)

        # Parse the rest of the string
        match = cls._NVRA_RE.match(nvra)
        if not match:
            message = "Invalid NEVRA string: {}".format(nevra)
            raise ValueError(message)

        arguments.update(
            (name, value)
            for name, value in match.groupdict().items()
            if value is not None
        )

        return cls(**arguments)

    # Derived attributes

    @property
    def dist(self) -> Optional["Metadata.DistTag"]:
        """RPM distribution tag.

        The dist tag is extracted from the release field.
        If none is found, None is returned.
        """

        try:
            return self.DistTag.from_release(self.release)
        except ValueError:
            return None

    @property
    def nvr(self) -> str:
        """:samp:`{name}-{version}-{release}` string of the RPM object"""

        return "{s.name}-{s.version}-{s.release}".format(s=self)

    @property
    def nevra(self) -> str:
        """:samp:`{name}-{epoch}:{version}-{release}.{arch}` string of the RPM object"""

        return "{s.name}-{s.epoch}:{s.version}-{s.release}.{s.arch}".format(s=self)

    @property
    def label(self) -> Tuple[str, str, str]:
        """Label compatible with RPM's C API."""

        return (str(self.epoch), self.version, self.release)

    @property
    def canonical_file_name(self):
        """Canonical base file name of a package with this metadata."""

        if self.epoch:
            format = "{s.name}-{s.epoch}:{s.version}-{s.release}.{s.arch}.rpm"
        else:
            format = "{s.name}-{s.version}-{s.release}.{s.arch}.rpm"

        return format.format(s=self)

    # Comparison methods
    def _compare(self, other: "Metadata", oper: CompareOperator) -> bool:
        """Generic comparison of two RPM-like objects.

        Keyword arguments:
            other: The object to compare with
            oper: The operator to use for the comparison.

        Returns:
            bool: The result of the comparison.
            NotImplemented: Incompatible operands.
        """

        try:
            if self.name == other.name:
                return oper(_rpm.labelCompare(self.label, other.label), 0)
            else:
                return oper(self.name, other.name)

        except AttributeError:
            return NotImplemented

    __eq__ = cast(CompareOperator, partialmethod(_compare, oper=operator.eq))
    __ne__ = cast(CompareOperator, partialmethod(_compare, oper=operator.ne))
    __lt__ = cast(CompareOperator, partialmethod(_compare, oper=operator.lt))
    __le__ = cast(CompareOperator, partialmethod(_compare, oper=operator.le))
    __gt__ = cast(CompareOperator, partialmethod(_compare, oper=operator.gt))
    __ge__ = cast(CompareOperator, partialmethod(_compare, oper=operator.ge))

    # String representations
    def __str__(self) -> str:
        return self.nevra

    # Transformations
    def with_simple_dist(self) -> "Metadata":
        """Create a copy of itself with simplified dist tag.

        Simplified dist tag is always in the form of :samp:`{distro}{major}`.

        Examples:
            >>> Metadata.from_nevra('abcde-1.0-1.el7_4').with_simple_dist().nvr
            'abcde-1.0-1.el7'
            >>> Metadata.from_nevra('binutils-3.6-4.el8+4').with_simple_dist().nvr
            'binutils-3.6-4.el8'
            >>> Metadata.from_nevra('abcde-1.0-1.fc27').with_simple_dist().nvr
            'abcde-1.0-1.fc27'
        """

        simple_release = self.DistTag._RE.sub(r".\g<id>\g<major>", self.release)
        return attr.evolve(self, release=simple_release)


#: Software Collection identifier (i.e. ``rh-postgresql96``)
SoftwareCollection = NewType("SoftwareCollection", str)


@runtime
class PackageLike(Protocol):
    """Any kind of RPM package descriptor or reference"""

    @property
    def metadata(self) -> Metadata:
        """The metadata associated with the object"""
        ...

    @property
    def scl(self) -> Optional[SoftwareCollection]:
        """Software Collection identifier (rh-postgresql96)"""
        ...


@report.serializable
@attr.s(slots=True, frozen=True, hash=True)
class LocalPackage:
    """Existing RPM package on local file system."""

    yaml_tag: ClassVar[str] = "!local"

    #: Resolved path to the RPM package
    path: Path = attr.ib(converter=_normalize_path)

    #: Metadata of the package
    metadata: Metadata = attr.ib(validator=instance_of(Metadata))

    #: SoftwareCollection this package is part of
    scl: Optional[SoftwareCollection] = attr.ib(default=None)

    @path.validator
    def _existing_file_path(self, _attribute, path):
        """The path must point to an existing file.

        Raises:
            FileNotFoundError: The path does not points to a file.
        """

        if not path.is_file():
            raise FileNotFoundError(path)

    @metadata.default
    def _file_metadata(self) -> Metadata:
        """Read metadata from an RPM file.

        Keyword arguments:
            file: The IO object to read the metadata from.
                It has to provide a file descriptor – in-memory
                files are unsupported.

        Returns:
            New instance of Metadata.
        """

        transaction = _rpm.TransactionSet()
        # Ignore missing signatures warning
        transaction.setVSFlags(_rpm._RPMVSF_NOSIGNATURES)

        with self.path.open(mode="rb") as file:
            header = transaction.hdrFromFdno(file.fileno())

        # Decode the metadata
        metadata = {
            "name": header[_rpm.RPMTAG_NAME].decode("utf-8"),
            "version": header[_rpm.RPMTAG_VERSION].decode("utf-8"),
            "release": header[_rpm.RPMTAG_RELEASE].decode("utf-8"),
            "epoch": header[_rpm.RPMTAG_EPOCHNUM],
        }

        # For source RPMs the architecture reported is a binary one
        # for some reason
        if header[_rpm.RPMTAG_SOURCEPACKAGE]:
            metadata["arch"] = "src"
        else:
            metadata["arch"] = header[_rpm.RPMTAG_ARCH].decode("utf-8")

        return Metadata(**metadata)

    # Path-like protocol
    def __fspath__(self) -> str:
        return str(self.path)

    # Representations
    def __str__(self):
        return self.__fspath__()

    @classmethod
    def to_yaml(
        cls, representer: yaml.Representer, instance: "LocalPackage"
    ) -> yaml.Node:
        node = representer.represent_data(instance.path)
        node.tag = cls.yaml_tag
        return node

    @classmethod
    def from_yaml(
        cls, constructor: yaml.Constructor, node: yaml.ScalarNode
    ) -> "LocalPackage":
        return cls(path=constructor.construct_scalar(node))


# Utility functions
def shorten_dist_tag(metadata: Metadata) -> Metadata:
    """Shorten release string by removing extra parts of dist tag.

    Examples:
        - abcde-1.0-1.el7_4 → abcde-1.0-1.el7
        - binutils-3.6-4.el8+4 → binutils-3.6-4.el8
        - abcde-1.0-1.fc27 → abcde-1.0-1.fc27

    Keyword arguments:
        metadata: The metadata to shorten.

    Returns:
        Potentially modified metadata.
    """

    return metadata.with_simple_dist()
