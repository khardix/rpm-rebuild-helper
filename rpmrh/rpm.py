"""RPM-related classes and procedures."""
import operator
import re
from functools import partialmethod
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import ClassVar
from typing import Tuple
from typing import Union

import attr
from attr.validators import instance_of

from .util import system_import

_rpm = system_import("rpm")

# type aliases and helpers
CompareOperator = Callable[[Any, Any], bool]


# .el7_4 format
LONG_DIST_RE = re.compile(
    r"""
    (\.         # short dist tag starts with a dot…
    [^\W\d_]+   # … followed by at least one letter…
    \d+)        # … and ended by at least one digit
    [^.]*  # any other characters up to the next dot
""",
    flags=re.VERBOSE,
)


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


@attr.s(slots=True, frozen=True, hash=True, cmp=False)
class LocalPackage:
    """Existing RPM package on local file system."""

    #: Resolved path to the RPM package
    path: Path = attr.ib(converter=_normalize_path)

    #: Metadata of the package
    metadata: Metadata = attr.ib(validator=instance_of(Metadata))

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

    # String representation
    def __str__(self):
        return self.__fspath__()


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

    return attr.evolve(metadata, release=LONG_DIST_RE.sub(r"\1", metadata.release))
