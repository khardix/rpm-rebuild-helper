"""Jenkins test runner integration"""

import logging
import re
from itertools import dropwhile
from typing import Iterator, Set
from urllib.parse import urljoin

import attr
import jenkins
import requests
from attr.validators import instance_of
from click import ClickException

from .. import rpm, util
from ..configuration import service


LOG = logging.getLogger(__name__)

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


# TODO Unify exceptions
class UnknownJob(ClickException):
    """No job with specified name was found on the server."""

    def __init__(
        self,
        server_url: str,
        job_name: str,
        *,
        message_format: str = '[{server_url}]: Job {job_name} not found',
    ):
        """Format the error message"""

        super().__init__(message_format.format(
            server_url=server_url,
            job_name=job_name,
        ))


class NoInstallLog(RuntimeError):
    """No install log was found in the build outputs."""


@service.register('jenkins', initializer='configure')
@attr.s(slots=True, frozen=True)
class Server:
    """Thin wrapper around Jenkins API"""

    #: API handle for low-level calls
    _handle = attr.ib(validator=instance_of(jenkins.Jenkins))

    #: requests.Session for direct HTTP communication
    _session = attr.ib(
        default=attr.Factory(util.net.default_requests_session),
        validator=instance_of(requests.Session),
    )

    @classmethod
    def configure(cls, url: str, **attributes):
        """Create a new server instance from text configuration.

        Keyword arguments:
            url: The URL of the Jenkins server.
            attributes: Other attributes, directly passed to __init__.

        Returns:
            New instance of Server object.
        """

        return cls(
            handle=jenkins.Jenkins(url),
            **attributes,
        )

    def tested_packages(self, job_name) -> Set[rpm.Metadata]:
        """Provide set of packages successfully tested by the specified job.

        Keyword arguments:
            job_name: The name of the job to query.

        Returns:
            Set of packages successfully tested by the specified job.

        Raises:
            UnknownJob: Specified job does not exist.
            NoInstallLog: Missing installation log, cannot parse the packages.
        """

        try:
            build = self._handle.get_job_info(job_name)['lastSuccessfulBuild']
        except jenkins.NotFoundException as exc:
            raise UnknownJob(self._handle.server, job_name) from exc

        if build is None:  # No successful build
            LOG.debug('No successful build for {} found'.format(job_name))
            return frozenset()

        log_url = urljoin(build['url'], 'artifact/results/{}/out')
        install_tests = 'install-all-pkgs', 'install'

        for url in map(log_url.format, install_tests):
            LOG.debug('Trying log URL {}'.format(url))
            response = self._session.get(url, stream=True)

            if not response.ok:
                continue

            response.encoding = 'utf-8'
            LOG.debug('Checking installed packages in {}'.format(url))
            break

        else:
            raise NoInstallLog('{}: No install log found'.format(build['url']))

        log_lines = response.iter_lines(decode_unicode=True)
        return frozenset(_extract_installed(log_lines))
