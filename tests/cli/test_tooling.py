"""Tests for the CLI tooling."""

from collections import namedtuple

import click
import pytest
from ruamel import yaml

import rpmrh.cli.tooling as tooling
from rpmrh import rpm


@pytest.fixture
def package_stream():
    """Prepared package stream"""

    metadata = [
        rpm.Metadata(name="test", version="2.1", release="3.el7"),
        rpm.Metadata(name="abcde", version="1.0", release="1.el7"),
        rpm.Metadata(name="abcde", version="2.0", release="1.el7"),
    ]

    return tooling.PackageStream(
        tooling.Package(scl=tooling.SCL(collection="test", el=7), metadata=m)
        for m in metadata
    )


@pytest.fixture
def yaml_structure(package_stream):
    """Expected YAML representation of package_stream"""

    structure = {}

    for pkg in sorted(package_stream._container):
        el_map = structure.setdefault(pkg.scl.el, {})
        scl_list = el_map.setdefault(pkg.scl.collection, [])
        scl_list.append(str(pkg.metadata))

    return structure


@pytest.fixture
def phase():
    """Filled test registry"""

    Service = namedtuple("Service", ["identification"])
    return {"repo": {"service": Service("simple"), "tags": ["simple-tag"]}}


def make_command(function, phase):
    """Turn a function into click Command"""

    context_settings = dict(obj={"source": phase})

    decorator = click.command(context_settings=context_settings)
    return decorator(function)


@pytest.fixture
def process_command(phase):
    """Dummy click command for tests of stream processing"""

    processor = tooling.stream_processor(lambda stream: stream, source="repo")

    return make_command(processor, phase)


@pytest.fixture
def generate_command(phase):
    """Dummy click command for tests of stream generation"""

    generator = tooling.stream_generator(lambda stream: stream, source="repo")

    return make_command(generator, phase)


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


def test_stream_expansion(process_command, package_stream):
    """All packages in a stream are expanded as expected"""

    # Manually apply the decorator
    ctx = process_command.make_context("test_stream_expansion", [])
    stream = ctx.invoke(process_command)(package_stream)

    def valid_package(package):
        valid_source = package.source["service"].identification == "simple"
        valid_destination = package.destination is None
        valid_metadata = package.metadata is not None

        return all((valid_source, valid_destination, valid_metadata))

    assert all(map(valid_package, stream))


def test_stream_generation(generate_command, package_stream):
    """Generator provides appropriate empty collections"""

    ctx = generate_command.make_context("test_stream_generation", [])
    stream = list(ctx.invoke(generate_command)(package_stream))

    def valid_package(package):
        source = package.source["service"].identification == "simple"
        destination = package.destination is None
        metadata = package.metadata is None

        return all((source, destination, metadata))

    assert all(map(valid_package, stream))
    assert len(stream) == 1
