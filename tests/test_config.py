"""Tests for the configuration mechanism"""

from io import StringIO
from pathlib import Path

import pytest
import toml

from rpmrh import config, service


@pytest.fixture
def registry():
    """Fresh configuration registry"""

    return dict()


@pytest.fixture
def source_type(registry):
    """Registered test source type."""

    @service.register('test', registry=registry)
    class Tested(dict):
        instance_ids = set()

        def register(self):
            Tested.instance_ids.add(id(self))

    return Tested


@pytest.fixture
def source_configuration(source_type):
    """Raw configuration for the test source."""

    return {
        'type': 'test',
        'scalar': 42,
        'sequence': ['Hello', 'World'],
        'mapping': {'lang': 'en_US'},
    }


@pytest.fixture
def config_file(source_configuration):
    """Single open configuration file."""

    contents = toml.dumps({'source': [source_configuration]})
    return StringIO(contents)


@pytest.fixture
def config_path_sequence(tmpdir, config_file):
    """Sequence of configuration file paths."""

    path = Path(str(tmpdir), 'test-source.toml')
    with path.open(mode='w', encoding='utf-8') as ostream:
        ostream.write(config_file.read())

    return [path]


def test_single_source_is_instantiated(
    registry,
    source_type,
    source_configuration
):
    """Single source configuration is properly interpreted."""

    instance = config.load_source(source_configuration, registry=registry)

    assert isinstance(instance, source_type)
    assert 'type' not in instance
    assert all(
        instance[i] == source_configuration[i]
        for i in ('scalar', 'sequence', 'mapping')
    ), instance


def test_config_file_is_interpreted(registry, source_type, config_file):
    """Configuration file is properly interpreted."""

    config.load_config_file(config_file, registry=registry)

    assert len(source_type.instance_ids) == 1


def test_config_paths_are_interpreted(
    registry,
    source_type,
    config_path_sequence
):
    """Sequence of configuration files is interpreted properly."""

    config.load_configuration(config_path_sequence, registry=registry)

    assert len(source_type.instance_ids) == 1
