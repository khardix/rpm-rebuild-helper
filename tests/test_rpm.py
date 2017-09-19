"""Test the rpmrh.rpm module."""

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


@pytest.fixture
def local_pkg(metadata, minimal_srpm_path) -> rpm.LocalPackage:
    """Provide LocalPackage object"""

    return rpm.LocalPackage(
        **attr.asdict(metadata),
        path=minimal_srpm_path,
    )


def test_construction_from_file(minimal_srpm_path):
    """Metadata can be read from open file."""

    with minimal_srpm_path.open(mode='rb') as istream:
        metadata = rpm.Metadata.from_file(istream)

    assert metadata.name == 'test'
    assert metadata.epoch == 0
    assert metadata.arch == 'src'


def test_nvr_format(metadata):
    """Ensure NVR is formatted as expected"""

    nvr_format = '{name}-{version}-{release}'

    assert metadata.nvr == nvr_format.format_map(attr.asdict(metadata))


def test_nevra_format(metadata):
    """Ensure that the NEVRA is formatted as expected"""

    nevra_format = '{name}-{epoch}:{version}-{release}.{arch}'

    assert metadata.nevra == nevra_format.format_map(attr.asdict(metadata))


def test_canonical_name_format(metadata):
    """Ensure that the canonical name is constructed properly"""

    if metadata.epoch:
        canonical_format = '{name}-{epoch}:{version}-{release}.{arch}.rpm'
    else:
        canonical_format = '{name}-{version}-{release}.{arch}.rpm'

    assert metadata.canonical_file_name == canonical_format.format_map(
        attr.asdict(metadata)
    )


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


def test_construction_from_path(minimal_srpm_path):
    """Metadata can be read for a file path."""

    metadata = rpm.LocalPackage.from_path(minimal_srpm_path)

    assert metadata.name == 'test'
    assert metadata.epoch == 0
    assert metadata.arch == 'src'
    assert metadata.path == minimal_srpm_path
