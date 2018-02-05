"""Jenkins test runner integration"""

import re
from itertools import dropwhile
from typing import Iterator

import attr
import jenkins
import requests
from attr.validators import instance_of

from .. import rpm, util
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


def _extract_installed(lines: Iterator[str]) -> Iterator[rpm.Metadata]:
    """Extracts installed packages from DNF log.

    This function looks for '*Installed:' header lines inside a log iterator.
    After a heading, each line up to the first empty one is expected
    to contain an package description in the format accepted by
    _parse_package_line().

    All such section are extracted from the log.
    The packages are reported in the order encountered.

    Keyword arguments:
        lines: The lines of the log to process.

    Yields:
        Found packages as rpm.Metadata.
    """

    while True:
        lines = dropwhile(lambda line: 'Installed:' not in line, lines)
        next(lines)  # drop the heading
        package_lines = iter(lines.__next__, '')
        yield from map(_parse_package_line, package_lines)


@service.register('jenkins')
@attr.s(slots=True, frozen=True)
class Server:
    """Remote jenkins server"""

    #: Base URL of the server
    url = attr.ib(validator=instance_of(str))

    #: API handle for low-level calls
    _handle = attr.ib(validator=instance_of(jenkins.Jenkins))

    #: requests.Session for direct HTTP communication
    _session = attr.ib(
        default=attr.Factory(util.net.default_requests_session),
        validator=instance_of(requests.Session),
    )

    @_handle.default
    def default_handle(self):
        """Construct the handle from URL."""

        return jenkins.Jenkins(self.url)
