"""Test the rpmrh.rpm module."""

import subprocess
from contextlib import suppress
from itertools import chain
from pathlib import Path
from textwrap import dedent

import attr
import pytest

from rpmrh import rpm


@pytest.fixture(params=[
    # Only required fields
    {'name': 'rpmrh', 'version': '0.1.0', 'release': '1.fc26'},
    # All possible fields
    {
        'name': 'rpmrh',
        'version': '0.1.0',
        'release': '1.fc26',
        'epoch': '1',
        'arch': 'x86_64',
    },
])
def metadata(request) -> rpm.Metadata:
    """Provide RPM metadata object"""

    return rpm.Metadata(**request.param)


@pytest.fixture(scope='session')
def minimal_spec_contents() -> str:
    """Text contents of a minimal SPEC file."""

    return dedent('''\
        Name:       test
        Version:    1.0
        Release:    1%{?dist}
        Summary:    Minimal spec for testing purposes

        Group:      Development/Testing
        License:    MIT
        URL:        http://test.example.com

        %description
        A minimal SPEC file for testing of RPM packaging.

        %prep

        %build

        %install

        %files

        %changelog
        * Thu Jun 22 2017 Jan Stanek <jstanek@redhat.com> 1.0-1
        - Initial package
    ''')


@pytest.fixture(scope='session')
def minimal_spec_path(tmpdir_factory, minimal_spec_contents) -> Path:
    """Provide a minimal SPEC file in temporary directory."""

    tmpdir = tmpdir_factory.mktemp('rpmbuild')

    with tmpdir.as_cwd():
        path = Path('test.spec')

        with path.open(mode='w', encoding='utf-8') as spec_file:
            spec_file.write(minimal_spec_contents)

        yield path

        with suppress(FileNotFoundError):
            path.unlink()


@pytest.fixture(scope='session')
def minimal_srpm(minimal_spec_path) -> Path:
    """Provide minimal SRPM for testing purposes."""

    # Build the SRPM using rpmbuild -bs
    workdir = minimal_spec_path.parent

    # Redefine working directories
    defines = chain.from_iterable(
        ('--define', '_{}dir {!s}'.format(stem, workdir))
        for stem in ['top', 'source', 'spec', 'build', 'srcrpm', 'rpm']
    )

    command = ['rpmbuild'] + list(defines) + ['-bs', str(minimal_spec_path)]

    subprocess.run(command)
    result, = workdir.glob('test-*.src.rpm')

    yield result

    with suppress(FileNotFoundError):
        result.unlink()


@pytest.fixture(scope='session')
def local_file(minimal_srpm) -> rpm.LocalFile:
    """Provide LocalFile for testing"""

    return rpm.LocalFile(minimal_srpm)


def test_nvr_format(metadata):
    """Ensure NVR is formatted as expected"""

    nvr_format = '{name}-{version}-{release}'

    assert metadata.nvr == nvr_format.format_map(attr.asdict(metadata))


def test_nevra_format(metadata):
    """Ensure that the NEVRA is formatted as expected"""

    nevra_format = '{name}-{epoch}:{version}-{release}.{arch}'

    assert metadata.nevra == nevra_format.format_map(attr.asdict(metadata))


def test_compare_as_expected(metadata):
    """Ensure that the comparison operators works as expected"""

    newer_version = attr.evolve(metadata, epoch=metadata.epoch+1)

    assert not metadata == newer_version
    assert metadata != newer_version
    assert metadata < newer_version
    assert metadata <= newer_version
    assert not metadata > newer_version
    assert not metadata >= newer_version


def test_not_compare_incompatible(metadata):
    """Incompatible type is reported as such."""

    incompatible_data = attr.asdict(metadata)

    metadata == incompatible_data


def test_metadata_are_hashable(metadata):
    """The metadata object is hashable and can be used in sets"""

    assert hash(metadata)
    assert len({metadata, metadata}) == 1


def test_local_file_construction_from_path(local_file):
    """rpm.LocalFile can be constructed from path."""

    # Fixture creates such file

    assert local_file.name == 'test'
    assert local_file.version == '1.0'
    # release changes with OS version
    assert local_file.release.startswith('1.')
    assert local_file.epoch == 0
    assert local_file.arch == 'src'


def test_local_file_string_representation(local_file):
    """String representation is full file path."""

    assert str(local_file) == str(local_file.path.resolve())
