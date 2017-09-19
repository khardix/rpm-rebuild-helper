"""Test communication with a koji build service"""

from configparser import ConfigParser
from textwrap import dedent
from pathlib import Path

import pytest

from rpmrh import rpm
from rpmrh.service import koji


@pytest.fixture
def configuration_profile():
    """Koji configuration profile"""

    return dedent('''\
    [cbs]

    ;url of XMLRPC server
    server = https://cbs.centos.org/kojihub/

    ;url of web interface
    weburl = https://cbs.centos.org/koji

    ;url of package download site
    topurl = http://cbs.centos.org/kojifiles

    ;path to the koji top directory
    topdir = /mnt/koji

    ;client certificate
    cert = ~/.centos.cert

    ;certificate of the CA that issued the client certificate
    ca = ~/.centos-server-ca.cert

    ;certificate of the CA that issued the HTTP server certificate
    serverca = /etc/pki/tls/certs/ca-bundle.trust.crt
    ''')


@pytest.fixture
def configuration_file(fs, configuration_profile):
    """Koji configuration profile on a fake FS"""

    conf_file_name = '/etc/koji.conf.d/cbs-koji.conf'

    fs.CreateFile(
        conf_file_name,
        contents=configuration_profile,
        encoding='utf-8',
    )

    yield Path(conf_file_name)

    fs.RemoveFile(conf_file_name)


@pytest.fixture
def built_package():
    """Metadata for Koji's built package"""

    return koji.BuiltPackage(
        id=18218,
        name='rh-ror50',
        version='5.0',
        release='5.el7',
        arch='x86_64',
    )


@pytest.fixture
def service(configuration_profile, betamax_parametrized_session):
    """Initialized koji.Service"""

    parser = ConfigParser()
    parser.read_string(configuration_profile)

    service = koji.Service(
        configuration=parser['cbs'],
        tag_prefixes={'sclo'},
    )

    service.session.rsession = betamax_parametrized_session

    return service


def test_built_package_from_mapping():
    """BuiltPackage can be constructed from raw mapping with extra data."""

    mapping = dict(
        id=18218,
        name='rh-ror50',
        version='5.0',
        release='5.el7',
        arch='x86_64',
        tags={'sclo7-rh-ror50-rh-candidate'},
        started='Tue, 01 Aug 2017 13:51:06 UTC',
        completed='Tue, 01 Aug 2017 13:54:43 UTC',
        nvr='rh-ror50-5.0-5.el7',
    )

    built = koji.BuiltPackage.from_mapping(mapping)

    assert built.id == mapping['id']
    assert built.nvr == mapping['nvr']


def test_built_package_from_incomplete_mapping():
    """BuiltPackage reports error on incomplete mapping initialization."""

    mapping = {'name': 'rh-ror50'}

    with pytest.raises(TypeError):
        koji.BuiltPackage.from_mapping(mapping)


def test_built_package_from_metadata(built_package, service):
    """BuiltPackage can fetch missing data from a service."""

    metadata = rpm.Metadata(
        name=built_package.name,
        version=built_package.version,
        release=built_package.release,
        arch=built_package.arch,
    )

    fetched = koji.BuiltPackage.from_metadata(
        service=service,
        original=metadata,
    )

    assert fetched.id == built_package.id


def test_service_from_profile_name(configuration_file):
    """Ensure that the koji configuration can be loaded from file."""

    service = koji.Service.from_config_profile('cbs', tag_prefixes={'sclo'})

    assert service.session
    assert service.path_info
    assert service.configuration['topurl'] == 'http://cbs.centos.org/kojifiles'


@pytest.mark.parametrize('tag_name,expected_nvr_set', {
    'sclo7-nginx16-rh-candidate':
        {'nginx16-1.2-2.el7', 'nginx16-nginx-1.6.2-3.el7'},
    'sclo6-rh-nginx110-rh-candidate':
        {'rh-nginx110-1.10-3.el6', 'rh-nginx110-nginx-1.10.2-2.el6'},
}.items())
def test_service_latest_builds(service, tag_name, expected_nvr_set):
    """Latest builds are properly extracted from the service"""

    results = {build.nvr for build in service.latest_builds(tag_name)}

    assert results == expected_nvr_set


def test_service_download(service, tmpdir, built_package):
    """Ensure the built package can be downloaded."""

    result = service.download(built_package, Path(str(tmpdir)))

    assert result == built_package
