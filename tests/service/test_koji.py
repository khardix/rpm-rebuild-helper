"""Test communication with a koji build service"""

from configparser import ConfigParser
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from textwrap import dedent

import attr
import pytest
from ruamel import yaml

from rpmrh import rpm
from rpmrh.service import koji
from rpmrh.service.abc import BuildFailure


class MockBuilder:
    """Mock implementations of koji functionality."""

    #: Valid targets
    targets = {'test'}

    #: Existing packages
    packages = {
        'test': {
            rpm.Metadata(
                name='test',
                version='1.0',
                release='1.test',
                arch='src',
            ),
        },
    }

    #: Prepared task results
    tasks = {
        hash('OK'): {
            'id': hash('OK'),
            'state': koji.koji.TASK_STATES['CLOSED'],
        },
        hash('FAIL'): {
            'id': hash('FAIL'),
            'state': koji.koji.TASK_STATES['FAILED'],
        },
    }

    def uploadWrapper(_self, _remote, _package, **_kwargs):
        """No return value -- skip"""
        pass

    def getBuildTarget(self, name):
        if name in self.targets:
            return {'name': name}
        else:
            return None

    def build(self, package_path, target_name, **_kwargs):
        """Return ID of successful or failed build, depending on package_path
        """

        assert target_name in self.targets

        existing_names = map(str, self.packages[target_name])
        already_built = any(n in package_path for n in existing_names)
        if already_built:
            return hash('FAIL')
        else:
            return hash('OK')

    def getTaskInfo(self, task_id):
        return self.tasks[task_id]

    def getBuild(self, build_map, **_kwargs):
        build_map.setdefault('id', hash('OK'))
        return build_map

    def getTaskResult(self, task_id):
        assert task_id == hash('FAIL')
        raise koji.koji.GenericError('Already built')


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


@pytest.fixture
def build_service(service):
    """Service with mocked session for build testing"""

    attr.set_run_validators(False)
    build_service = attr.evolve(service, session=MockBuilder())
    attr.set_run_validators(True)

    return build_service


@pytest.fixture
def new_package(minimal_srpm_path):
    """Package not yet built in the service."""

    return rpm.LocalPackage.from_path(minimal_srpm_path)


@pytest.fixture
def existing_package(new_package):
    """Package already existing in build service."""

    desired = next(iter(MockBuilder.packages['test']))
    desired_path = new_package.path.with_name('{.nevra}.rpm'.format(desired))

    desired_path.touch()

    yield attr.evolve(
        new_package,
        **attr.asdict(desired),
        path=desired_path,
    )

    desired_path.unlink()


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


@pytest.mark.parametrize('tag_name', [
    # The error found in these tags
    'sclo7-rh-nodejs4-rh-candidate',
    'sclo7-rh-perl524-rh-candidate',
])
def test_latest_builds_are_not_obsoletes(service, tag_name):
    """Latest builds do not report obsolete packages.

    koji.ClientSession.latest_builds apparently orders the builds by time,
    not by NVR.
    """

    def obsolete(package, existing_map):
        return (
            package.name in existing_map
            and existing_map[package.name] > package
        )

    existing_raw = service.session.listTagged(tag_name)
    existing = map(koji.BuiltPackage.from_mapping, existing_raw)
    existing = groupby(sorted(existing), key=attrgetter('name'))
    existing = {k: max(g) for k, g in existing}

    latest = list(service.latest_builds(tag_name))

    obsoletes = [
        {
            'existing': existing[pkg.name].nevra,
            'latest': pkg.nevra,
        }
        for pkg in latest if obsolete(pkg, existing)
    ]

    assert not obsoletes, '\n' + yaml.dump(obsoletes, default_flow_style=False)


def test_service_download(service, tmpdir, built_package):
    """Ensure the built package can be downloaded."""

    result = service.download(built_package, Path(str(tmpdir)))

    assert result == built_package


def test_build_reports_nonexistent_target(build_service, new_package):
    """Nonexistent build target is reported"""

    with pytest.raises(ValueError):
        build_service.build('nonexistent', new_package)


def test_new_package_builds_successfully(build_service, new_package):
    """Package not present in build service builds successfully"""

    result_package = build_service.build('test', new_package)

    assert result_package
    assert result_package == new_package


def test_existing_package_build_raises(build_service, existing_package):
    """Already built package raises an exception"""

    with pytest.raises(BuildFailure):
        build_service.build('test', existing_package)
