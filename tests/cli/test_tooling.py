"""Tests for the CLI tooling."""

from collections import namedtuple

import click
import pytest
from pytrie import StringTrie
from ruamel import yaml

import rpmrh.cli.tooling as tooling
from rpmrh import rpm
from rpmrh.configuration import service


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


@pytest.fixture
def instance_registry():
    """Filled test registry"""

    Service = namedtuple('Service', ['identification'])
    index_data = StringTrie(test=Service('simple'))
    return service.Registry(
        index={'tag': service.Index('tag', index_data)},
        alias={'tag': {}},
    )


@pytest.fixture
def command(instance_registry):
    """Dummy click command for tests of stream processing"""

    context_settings = dict(obj=tooling.Parameters(
        cli_options={'source': 'test', 'destination': None},
        main_config={},
        service_registry=instance_registry,
    ))

    @click.command(context_settings=context_settings)
    @tooling.stream_processor(source='tag')
    def dummy(stream):
        return stream

    return dummy


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


def test_stream_expansion(command, package_stream):
    """All packages in a stream are expanded as expected"""

    ctx = command.make_context('test_stream_expansion', [])
    stream = ctx.invoke(command)(package_stream)

    def valid_package(package):
        valid_source = package.source.service.identification == 'simple'
        valid_destination = package.destination is None

        return valid_source and valid_destination

    assert all(map(valid_package, stream))
