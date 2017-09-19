"""Test the DNF interface"""

from pathlib import Path

import dnf as system_dnf
import pytest

from rpmrh import rpm
from rpmrh.service import dnf


@pytest.fixture
def base():
    """Provide empty, configured dnf.Base."""

    with system_dnf.Base() as base:
        yield base


@pytest.fixture
def raw_package(base, minimal_srpm_path):
    """Provide raw dnf.Package."""

    base.fill_sack(load_system_repo=False, load_available_repos=False)
    pkg, = base.add_remote_rpms(map(str, [minimal_srpm_path]))
    base.reset(sack=True)

    return pkg


@pytest.fixture
def repo_configuration(minimal_repository_url):
    """Provide repository configuration"""

    return {
        'name': 'test-repo',
        'baseurl': minimal_repository_url,
    }


@pytest.fixture
def configured_group(repo_configuration):
    """Provide RepoGroup with configured repositories."""

    return dnf.RepoGroup.configured([repo_configuration])


def test_package_is_converted(raw_package):
    """Raw dnf.Package is successfully converted"""

    metadata = dnf.convert_metadata(raw_package)

    assert isinstance(metadata, rpm.Metadata)
    assert metadata.name == raw_package.name
    assert metadata.epoch == raw_package.epoch


def test_repo_builds_are_reported(configured_group, minimal_srpm_path):
    """Builds in configured repos are reported."""

    builds = list(configured_group.latest_builds('test-repo'))

    assert len(builds) == 1

    build, = builds

    assert isinstance(build, rpm.Metadata)
    assert build == rpm.LocalPackage.from_path(minimal_srpm_path)


def test_packages_are_downloaded(
    configured_group,
    minimal_srpm_path,
    tmpdir_factory
):
    """Packages can be downloaded from the repo"""

    target_dir = Path(str(tmpdir_factory.mktemp('dnf-download')))
    request = rpm.LocalPackage.from_path(minimal_srpm_path)

    result = configured_group.download(request, target_dir)

    assert result
    assert result.path.relative_to(target_dir)
    assert result == request
