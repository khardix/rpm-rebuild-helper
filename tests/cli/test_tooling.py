"""Tests for the CLI tooling."""

import pytest
from ruamel import yaml

import rpmrh.cli.tooling as tooling
from rpmrh import rpm


@pytest.fixture
def package_stream():
    """Prepared package stream"""

    metadata = [
        rpm.Metadata(name='test', version='2.1', release='3.el7'),
        rpm.Metadata(name='abcde', version='1.0', release='1.el7'),
        rpm.Metadata(name='abcde', version='2.0', release='1.el7'),
    ]

    return tooling.PackageStream(
        tooling.Package(collection='test', el=7, metadata=m)
        for m in metadata
    )


@pytest.fixture
def yaml_structure(package_stream):
    """Expected YAML representation of package_stream"""

    structure = {}

    for pkg in sorted(package_stream._container):
        el_map = structure.setdefault(pkg.el, {})
        scl_list = el_map.setdefault(pkg.collection, [])
        scl_list.append(str(pkg.metadata))

    return structure


def test_stream_iteration(package_stream):
    """The iteration is performed in the expected order."""

    assert list(package_stream) == sorted(package_stream._container)


def test_stream_consumption(package_stream):
    """Package stream can be (re-)created by consuming an iterator."""

    iterator = iter(package_stream)
    result = tooling.PackageStream.consume(iterator)

    assert result is not package_stream
    assert result == package_stream


def test_stream_serialization(package_stream, yaml_structure):
    """PackageStream can be serialized into YAML."""

    result = yaml.safe_load(package_stream.to_yaml())

    assert result == yaml_structure


def test_stream_deserialization(package_stream, yaml_structure):
    """PackageStream can be created from YAML representation."""

    result = tooling.PackageStream.from_yaml(yaml.safe_dump(yaml_structure))

    assert result is not package_stream
    assert result == package_stream
