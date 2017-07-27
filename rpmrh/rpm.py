"""RPM-related classes and procedures."""

import operator
import os
from functools import partialmethod
from pathlib import Path
from typing import Callable, Tuple, TypeVar, Union

import attr
from attr.validators import instance_of, optional

from .util import system_import

_rpm = system_import('rpm')

# type aliases for comparison functions
CompareOperator = Callable[[TypeVar('T'), TypeVar('T')], bool]
CompareResult = Union[bool, type(NotImplemented)]


@attr.s(slots=True, cmp=False, frozen=True, hash=True)
class Metadata:
    """Generic RPM metadata.

    This class should act as a basis for all the RPM-like objects,
    providing common comparison and other "dunder" methods.
    """

    name = attr.ib(validator=instance_of(str))
    version = attr.ib(validator=instance_of(str))
    release = attr.ib(validator=instance_of(str))

    epoch = attr.ib(validator=optional(instance_of(int)), default=0, convert=int)  # noqa: E501
    arch = attr.ib(validator=optional(instance_of(str)), default='src')

    # Derived attributes

    @property
    def nvr(self) -> str:
        """Name-Version-Release string of the RPM object"""

        return '{s.name}-{s.version}-{s.release}'.format(s=self)

    @property
    def nevra(self) -> str:
        """Name-Epoch:Version-Release.Architecture string of the RPM object"""

        return '{s.name}-{s.epoch}:{s.version}-{s.release}.{s.arch}'.format(
            s=self
        )

    @property
    def label(self) -> Tuple[int, str, str]:
        """Label compatible with RPM's C API."""

        return (str(self.epoch), self.version, self.release)

    # Comparison methods
    def _compare(self, other: 'Metadata', oper: CompareOperator) -> CompareResult:  # noqa: E501
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

    __eq__ = partialmethod(_compare, oper=operator.eq)
    __ne__ = partialmethod(_compare, oper=operator.ne)
    __lt__ = partialmethod(_compare, oper=operator.lt)
    __le__ = partialmethod(_compare, oper=operator.le)
    __gt__ = partialmethod(_compare, oper=operator.gt)
    __ge__ = partialmethod(_compare, oper=operator.ge)

    def __str__(self):
        """Pretty-print in the full NEVRA form."""

        return self.nevra


@attr.s(slots=True, cmp=False, frozen=True, init=False)
class LocalFile(Metadata):
    """RPM file on a local file system.

    Note that after the initial creation, the metadata and the file name
    are NOT kept in sync. This mirrors the fact that renaming the RPM
    file will not change the metadata within.
    """

    #: Full path to the local file
    path = attr.ib(validator=instance_of(Path), default=Path.cwd())

    def __init__(self, full_path: Path) -> 'LocalFile':
        """Construct the LocalFile from full path.

        Keyword arguments:
            full_path: Path to the file to represent as LocalFile.

        Returns:
            New initialized instance.
        """

        header = _read_rpm_header(full_path)
        arguments = {
            'name': header[_rpm.RPMTAG_NAME].decode('utf-8'),
            'version': header[_rpm.RPMTAG_VERSION].decode('utf-8'),
            'release': header[_rpm.RPMTAG_RELEASE].decode('utf-8'),
            'epoch': header[_rpm.RPMTAG_EPOCHNUM],
        }

        # the header reports binary architecture on source RPMs
        if header[_rpm.RPMTAG_SOURCEPACKAGE]:
            arguments['arch'] = 'src'
        else:
            arguments['arch'] = header[_rpm.RPMTAG_ARCH]

        super(LocalFile, self).__init__(**arguments)
        # Subvert frozen object
        object.__setattr__(self, 'path', full_path)

        attr.validate(self)

    def __str__(self):
        """Pretty-print the absolute path"""

        return str(self.path.resolve())

    @property
    def header(self) -> _rpm.hdr:
        """Raw RPM header"""

        return _read_rpm_header(self.path)


# Private helper functions

def _read_rpm_header(path: Path) -> _rpm.hdr:
    """Extract a header from an RPM file.

    Keyword arguments:
        path: Path to an RPM file to read.

    Returns:
        Header of the RPM file.
    """

    ts = _rpm.TransactionSet()
    # Ignore missing signatures
    ts.setVSFlags(_rpm._RPMVSF_NOSIGNATURES)

    fd = os.open(str(path), os.O_RDONLY)  # need file descriptor :(
    try:
        return ts.hdrFromFdno(fd)
    finally:
        os.close(fd)
