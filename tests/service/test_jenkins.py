import jenkins
import pytest

from rpmrh import service

#: Build containing install-all-pkgs artifact
ALL_PKGS_URL = 'https://ci.centos.org/job/SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64/'  # noqa: E501
#: Build containing only install artifact
INSTALL_ONLY_URL = 'https://ci.centos.org/job/SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64/'  # noqa: E501
#: Build contains multiple package listings in install artifact
MULTIPLE_SECTION_URL = 'https://ci.centos.org/job/SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64/'  # noqa: E501


@pytest.fixture
def server(mocker):
    url = 'https://ci.centos.org/'
    job_fmt = 'SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64'
    handle = mocker.Mock(spec=jenkins.Jenkins(url))

    return service.jenkins.Server(
        url=url,
        job_name_format=job_fmt,
        handle=handle,
    )


def test_server_creation(server):
    """Server instance can be created"""

    assert server
