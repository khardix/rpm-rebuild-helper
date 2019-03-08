"""Test the rpmrh.rpm module."""
import sys
from types import MappingProxyType

import attr
import pytest

from rpmrh import rpm


METADATA_PARAMETERS = [
    # Only required fields
    MappingProxyType({"name": "rpmrh", "version": "0.1.0", "release": "1.fc26"}),
    # All possible fields
    MappingProxyType(
        {
            "name": "rpmrh",
            "version": "0.1.0",
            "release": "1.fc26",
            "epoch": "1",
            "arch": "x86_64",
        }
    ),
]


@pytest.fixture(params=METADATA_PARAMETERS)
def metadata(request) -> rpm.Metadata:
    """Provide RPM metadata object"""

    return rpm.Metadata(**request.param)


@pytest.fixture(
    params=METADATA_PARAMETERS
    + [
        # epoch in weird place
        "1:rpmrh-0.1.0-1.fc26.x86_64"
    ]
)
def nevra(request) -> str:
    """Provide NEVRA string for metadata creation"""

    if isinstance(request.param, str):
        return request.param

    format_map = request.param.copy()

    # Pre-formatting
    if "epoch" in format_map:
        format_map["epoch"] = "{epoch}:".format_map(format_map)
    else:
        format_map["epoch"] = ""

    if "arch" in format_map:
        format_map["arch"] = ".{arch}".format_map(format_map)
    else:
        format_map["arch"] = ""

    return "{name}-{epoch}{version}-{release}{arch}".format_map(format_map)


@pytest.fixture
def local_pkg(metadata, minimal_srpm_path) -> rpm.LocalPackage:
    """Provide LocalPackage object"""

    return rpm.LocalPackage(path=minimal_srpm_path, metadata=metadata)


def test_nvr_format(metadata):
    """Ensure NVR is formatted as expected"""

    nvr_format = "{name}-{version}-{release}"

    assert metadata.nvr == nvr_format.format_map(attr.asdict(metadata))


def test_nevra_format(metadata):
    """Ensure that the NEVRA is formatted as expected"""

    nevra_format = "{name}-{epoch}:{version}-{release}.{arch}"

    assert metadata.nevra == nevra_format.format_map(attr.asdict(metadata))


def test_canonical_name_format(metadata):
    """Ensure that the canonical name is constructed properly"""

    if metadata.epoch:
        canonical_format = "{name}-{epoch}:{version}-{release}.{arch}.rpm"
    else:
        canonical_format = "{name}-{version}-{release}.{arch}.rpm"

    assert metadata.canonical_file_name == canonical_format.format_map(
        attr.asdict(metadata)
    )


def test_compare_as_expected(metadata):
    """Ensure that the comparison operators works as expected"""

    newer_version = attr.evolve(metadata, epoch=metadata.epoch + 1)

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


def test_construction_from_nevra(nevra):
    """Metadata can be obtained by parsing a NEVRA string."""

    metadata = rpm.Metadata.from_nevra(nevra)
    print(nevra, "->", repr(metadata), file=sys.stderr)

    assert metadata.name == "rpmrh"
    assert metadata.epoch in {0, 1}
    assert metadata.version == "0.1.0"
    assert metadata.release == "1.fc26"
    assert metadata.arch in {"src", "x86_64"}


def test_construction_from_file_name(nevra):
    """Metadata can be obtained from base file name."""

    filename = ".".join((nevra, "rpm"))

    assert rpm.Metadata.from_nevra(nevra) == rpm.Metadata.from_nevra(filename)


def test_construction_from_path(minimal_srpm_path):
    """Metadata can be read for a file path."""

    package = rpm.LocalPackage(minimal_srpm_path)

    assert package.metadata.name == "test"
    assert package.metadata.epoch == 0
    assert package.metadata.arch == "src"
    assert package.path == minimal_srpm_path


@pytest.mark.parametrize(
    "original_nvr,result_nvr",
    [
        ("abcde-1.0-1.el7_4", "abcde-1.0-1.el7"),
        ("binutils-3.6-4.el8+4", "binutils-3.6-4.el8"),
        ("abcde-1.0-1.fc27", "abcde-1.0-1.fc27"),
    ],
)
def test_shoten_dist_tag_works(original_nvr, result_nvr):
    """Ensure that the dist tag is simplified correctly."""

    original = rpm.Metadata.from_nevra(original_nvr)
    result = rpm.shorten_dist_tag(original)

    assert result.nvr == result_nvr
