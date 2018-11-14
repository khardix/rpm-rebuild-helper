from types import MappingProxyType

import jenkins
import pytest

from rpmrh import service, rpm

pytestmark = pytest.mark.filterwarnings(
    "ignore:betamax_parametrized:DeprecationWarning"
)

# FIXME Separation to ALL_PKGS and INSTALL_ONLY no longer makes sense

#: Job containing install-all-pkgs artifact
ALL_PKGS = MappingProxyType(
    {
        "url": "https://ci.centos.org/job/SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64/",  # noqa: E501
        "name": "SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64",
        "format": MappingProxyType({"collection": "rh-java-common", "el": 7}),
        "lastSuccessfulBuild": MappingProxyType(
            {
                "number": 94,
                "url": "https://ci.centos.org/job/SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64/94/",  # noqa: E501
                "packages": frozenset(
                    map(
                        rpm.Metadata.from_nevra,
                        (
                            "rh-java-common-1.1-47.el7.src.rpm",
                            "rh-java-common-easymock3-3.3-1.5.el7.src.rpm",
                            "rh-java-common-lucene5-5.4.1-2.4.el7.src.rpm",
                        ),
                    )
                ),
            }
        ),
    }
)
#: Job containing only install artifact
INSTALL_ONLY = MappingProxyType(
    {
        "url": "https://ci.centos.org/job/SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64/",  # noqa: E501
        "name": "SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64",
        "format": MappingProxyType({"collection": "devtoolset-7", "el": 7}),
        "lastSuccessfulBuild": MappingProxyType(
            {
                "number": 46,
                "url": "https://ci.centos.org/job/SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64/46/",  # noqa: E501
                "packages": frozenset(
                    map(
                        rpm.Metadata.from_nevra,
                        (
                            "CUnit-2.1.3-13.el7.src.rpm",
                            "devtoolset-7-gcc-7.2.1-1.el7.sc1.src.rpm",
                            "maven30-icc-profiles-openicc-1.3.1-5.8.el7.src.rpm",
                        ),
                    )
                ),
            }
        ),
    }
)
#: Job with no successful builds
NO_SUCCESS = MappingProxyType(
    {
        "url": "https://ci.centos.org/job/SCLo-pkg-rh-eclipse46-rh-C6-testing-x86_64/",  # noqa: E501
        "name": "SCLo-pkg-rh-eclipse46-rh-C6-testing-x86_64",
        "format": MappingProxyType({"collection": "rh-eclipse46", "el": 6}),
        "lastSuccessfulBuild": None,
    }
)

#: Build with single install section
SINGLE_SECTION = ALL_PKGS["lastSuccessfulBuild"]
#: Build contains multiple package listings in install artifact
MULTIPLE_SECTION = INSTALL_ONLY["lastSuccessfulBuild"]

# Parametrization sequences
ALL_JOBS = ALL_PKGS, INSTALL_ONLY, NO_SUCCESS
ALL_BUILDS = SINGLE_SECTION, MULTIPLE_SECTION


@pytest.fixture
def server(mocker, betamax_session):
    url = "https://ci.centos.org/"
    handle = mocker.Mock(spec=jenkins.Jenkins(url))
    session = betamax_session

    def get_job_info(name):
        try:
            return {j["name"]: j for j in ALL_JOBS}[name]
        except KeyError as err:
            raise jenkins.NotFoundException(*err.args) from None

    handle.get_job_info.side_effect = get_job_info

    return service.jenkins.Server(handle=handle, session=session)


def test_server_creation(server):
    """Server instance can be created"""

    assert server


def test_server_creation_from_configuration(server, betamax_session):
    """Server instance can be created from text configuration"""

    configuration = {"url": "https://ci.centos.org/", "session": betamax_session}

    configured = service.jenkins.Server.configure(**configuration)

    assert configured._handle.server == configuration["url"]


@pytest.mark.parametrize("job_name", ["job_with_ridiculous_name"])
def test_tested_packages_report_wrong_job_name(server, job_name):
    """Wrong job name causes an exception."""

    with pytest.raises(service.jenkins.UnknownJob):
        server.tested_packages(job_name)


@pytest.mark.parametrize("job", [NO_SUCCESS])
def test_tested_packages_handles_no_successfull_build(server, job):
    """Job with no successful build is handled gracefully."""

    assert server.tested_packages(job["name"]) == frozenset()


@pytest.mark.parametrize("job", [ALL_PKGS, INSTALL_ONLY])
def test_tested_packages_reports_expected_packages(server, job):
    """Expected packages are extracted from a job."""

    expected = job["lastSuccessfulBuild"]["packages"]
    actual = server.tested_packages(job["name"])
    assert actual >= expected, "Missing packages: {}".format(expected - actual)
