from types import MappingProxyType
from urllib.parse import urljoin

import jenkins
import pytest

from rpmrh import service, rpm

#: Job containing install-all-pkgs artifact
ALL_PKGS = MappingProxyType({
    'url': 'https://ci.centos.org/job/SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64/',  # noqa: E501
    'name': 'SCLo-pkg-rh-java-common-rh-C7-candidate-x86_64',
    'format': MappingProxyType({'collection': 'rh-java-common', 'el': 7}),
})
#: Job containing only install artifact
INSTALL_ONLY = MappingProxyType({
    'url': 'https://ci.centos.org/job/SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64/',  # noqa: E501
    'name': 'SCLo-pkg-devtoolset-7-rh-C7-buildlogs-x86_64',
    'format': MappingProxyType({'collection': 'devtoolset-7', 'el': 7}),
})

#: Build with single install section
SINGLE_SECTION = MappingProxyType(dict(
    ALL_PKGS,
    url=urljoin(ALL_PKGS['url'], '90/artifact/results/install-all-pkgs/out'),
    packages=frozenset(map(rpm.Metadata.from_nevra, (
        'rh-java-common-scldevel-1.1-47.el7.x86_64',
        'maven30-scldevel-1.1-27.el7.x86_64',
        'rh-java-common-lucene-replicator-4.8.0-6.9.el7.noarch',
    ))),
))
#: Build contains multiple package listings in install artifact
MULTIPLE_SECTION = MappingProxyType(dict(
    INSTALL_ONLY,
    url=urljoin(INSTALL_ONLY['url'], '42/artifact/results/install/out'),
    packages=frozenset(map(rpm.Metadata.from_nevra, (
        'centos-release-scl-rh-2-2.el7.centos.noarch',
        '1:devtoolset-7-make-4.2.1-2.el7.sc1.x86_64',
        'devtoolset-7-libstdc++-devel-7.2.1-1.el7.sc1.x86_64',
    ))),
))

# Parametrization sequences
ALL_JOBS = ALL_PKGS, INSTALL_ONLY
ALL_BUILDS = SINGLE_SECTION, MULTIPLE_SECTION


@pytest.fixture
def server(mocker):
    url = 'https://ci.centos.org/'
    handle = mocker.Mock(spec=jenkins.Jenkins(url))

    handle.get_job_info.side_effect = \
        lambda name: {j['name']: j for j in ALL_JOBS}[name]

    return service.jenkins.Server(
        url=url,
        handle=handle,
    )


def test_server_creation(server):
    """Server instance can be created"""

    assert server


@pytest.mark.parametrize('line,expected_metadata', [
    (
        'java-1.7.0-openjdk.x86_64 1:1.7.0.161-2.6.12.0.el7_4',
        rpm.Metadata(
            name='java-1.7.0-openjdk',
            epoch=1,
            version='1.7.0.161',
            release='2.6.12.0.el7_4',
            arch='x86_64',
        ),
    ),
    (
        'maven30-maven-artifact.noarch 0:2.2.1-47.11.el7',
        rpm.Metadata(
            name='maven30-maven-artifact',
            epoch=0,
            version='2.2.1',
            release='47.11.el7',
            arch='noarch',
        ),
    ),
])
def test_parse_package_line_accepts_correct_line(line, expected_metadata):
    """YUM/DNF package line parsing accepts correct lines"""

    assert service.jenkins._parse_package_line(line) == expected_metadata


@pytest.mark.parametrize('line', [
    '',
    'Dependency Installed:',
    'Installing : 1:perl-parent-0.225-244.el7.noarch        1/595',
])
def test_parse_package_line_reports_unexpected_line(line):
    """YUM/DNF package line parsing raises on unexpected line"""

    with pytest.raises(ValueError):
        service.jenkins._parse_package_line(line)


@pytest.mark.parametrize('build', ALL_BUILDS)
def test_extract_installed_lists_expected_packages(
    betamax_parametrized_session,
    build,
):
    """Expected packages are extracted from a log."""

    response = betamax_parametrized_session.get(build['url'])
    response.raise_for_status()
    response.encoding = 'utf-8'

    log_lines = response.iter_lines(decode_unicode=True)
    extracted = set(service.jenkins._extract_installed(log_lines))

    assert build['packages'].issubset(extracted)
