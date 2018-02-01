"""Jenkins test runner integration"""

import re

import attr
import jenkins
from attr.validators import instance_of

from .. import rpm
from ..configuration import service

#: RE of package lines in YUM/DNF logs
PKG_LINE_RE = re.compile('''
    (?P<name>\S+)            # package name
    (?:\.(?P<arch>\w+))     # package architecture
    \s+                     # white-space separator
    (?P<epoch>\d+):         # required package epoch
    (?P<version>[\w.]+)-    # package version
    (?P<release>\w+(?:\.[\w+]+)+)  # package release, with required dist tag
''', flags=re.VERBOSE)


def _parse_package_line(line: str) -> rpm.Metadata:
    """Parse a DNF log line with package information.

    The expected format of the line is::

        {name}.{arch} {epoch}:{version}-{release}

    Keyword arguments:
        line: The line to parse.

    Returns:
        The parsed metadata.

    Raises:
        ValueError: The line is not in the expected format.
    """

    match = PKG_LINE_RE.search(line)

    if not match:
        raise ValueError('Unexpected log line: ' + line)

    return rpm.Metadata(**match.groupdict())


@service.register('jenkins')
@attr.s(slots=True, frozen=True)
class Server:
    """Remote jenkins server"""

    #: Base URL of the server
    url = attr.ib(validator=instance_of(str))

    #: API handle for low-level calls
    _handle = attr.ib(validator=instance_of(jenkins.Jenkins))

    @_handle.default
    def default_handle(self):
        """Construct the handle from URL."""

        return jenkins.Jenkins(self.url)
