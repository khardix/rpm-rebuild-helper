"""Jenkins test runner integration"""
import logging
from typing import FrozenSet
from urllib.parse import urljoin

import attr
import jenkins
import requests
from attr.validators import instance_of

from .. import rpm
from .. import util
from ..configuration import service
from ..exception import UserError


LOG = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class UnknownJob(UserError):
    """No job with specified name was found on the server."""

    lead = "Jenkins error"

    #: URL of the queried server
    server_url = attr.ib(validator=instance_of(str))

    #: Name of the missing job
    job_name = attr.ib(validator=instance_of(str))

    def __attr_post_init__(self):
        super(UnknownJob, self).__init__(self.format_message())

    def format_message(self):
        fmt = "No job named {job_name} found at {server_url}"
        return fmt.format_map(attr.asdict(self))


class NoSourcePackages(RuntimeError):
    """No source package listing was found in the build outputs."""


@service.register("jenkins", initializer="configure")
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

        return cls(handle=jenkins.Jenkins(url), **attributes)

    def tested_packages(self, job_name) -> FrozenSet[rpm.Metadata]:
        """Provide set of packages successfully tested by the specified job.

        Keyword arguments:
            job_name: The name of the job to query.

        Returns:
            Set of packages successfully tested by the specified job.

        Raises:
            UnknownJob: Specified job does not exist.
            NoSourcePackages: No source package listing in build output,
                nothing to parse.
        """

        try:
            build = self._handle.get_job_info(job_name)["lastSuccessfulBuild"]
        except (
            jenkins.NotFoundException,
            jenkins.JenkinsException,
            requests.exceptions.HTTPError,
        ) as exc:
            raise UnknownJob(str(self._handle.server), job_name) from exc

        if build is None:  # No successful build
            LOG.debug("No successful build for {} found".format(job_name))
            return frozenset()

        log_url = urljoin(build["url"], "artifact/results/source-packages.txt")

        try:
            response = self._session.get(log_url, stream=True)
            response.raise_for_status()
        except requests.HTTPError as error:
            message = "{job}#{number}: Cannot open source packages: {reason}"
            raise NoSourcePackages(
                message.format(
                    job=job_name, number=build["number"], reason=error.response.reason
                )
            ) from error

        return frozenset(
            rpm.Metadata.from_nevra(line)
            for line in response.iter_lines(decode_unicode=True)
        )
