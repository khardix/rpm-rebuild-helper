"""Jenkins test runner integration"""

import attr
import jenkins
from attr.validators import instance_of

from ..configuration import service


@service.register('jenkins')
@attr.s(slots=True, frozen=True)
class Server:
    """Remote jenkins server"""

    #: Base URL of the server
    url = attr.ib(validator=instance_of(str))

    #: Format of the job name
    job_name_format = attr.ib(validator=instance_of(str))

    #: API handle for low-level calls
    _handle = attr.ib(validator=instance_of(jenkins.Jenkins))

    @_handle.default
    def default_handle(self):
        """Construct the handle from URL."""

        return jenkins.Jenkins(self.url)
