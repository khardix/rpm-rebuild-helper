"""Tests the validity of runtime configuration."""

from io import BytesIO

import pytest
import pytoml as toml
from pyfakefs.fake_pathlib import FakePath as Path
from xdg.BaseDirectory import xdg_config_home

import rpmrh.configuration.runtime as runtime
from rpmrh import RESOURCE_ID


@pytest.fixture
def valid_main_configuration():
    """Valid configuration dictionary"""

    return {
        'remote': {
            'collection_list': 'https://example.com/collections',
        },
    }


@pytest.fixture
def disabled_pkg_resources(monkeypatch):
    """Disables use of pkg_resources"""

    monkeypatch.setattr(
        'rpmrh.util.filesystem.resource_stream',
        lambda *__: BytesIO(),
    )
    monkeypatch.setattr(
        'rpmrh.util.filesystem.resource_listdir',
        lambda *__: [],
    )

    yield


@pytest.fixture
def valid_main_configuration_paths(
    disabled_pkg_resources,
    fs,
    valid_main_configuration,
):
    """Search paths for main configuration"""

    # fake user files
    conf_path = Path(xdg_config_home, RESOURCE_ID, runtime.CONF_BASE_NAME)
    conf_content = toml.dumps(valid_main_configuration)

    fs.CreateFile(str(conf_path), contents=conf_content, encoding='utf-8')

    yield [conf_path.parent]


@pytest.fixture
def valid_service_paths(
    disabled_pkg_resources,
    fs,
    valid_configuration_seq,
):
    """Search paths for service configuration"""

    service_paths = []

    for order, conf in enumerate(valid_configuration_seq):
        # Assemble name and path to the configuration pseudofile
        base_name = '{ord}{ext}'.format(ord=order, ext=runtime.SERVICE_EXT)
        path = Path(xdg_config_home, RESOURCE_ID, base_name)

        # Create the fake file and append its directory to search paths
        fs.CreateFile(path, contents=toml.dumps(conf), encoding='utf-8')
        service_paths.append(path.parent)

    return service_paths


def test_valid_configuration_is_loaded(valid_main_configuration_paths):
    """Valid configuration files are loaded"""

    configuration = runtime.load_configuration(
        search_path_seq=valid_main_configuration_paths,
    )

    assert 'collection_list' in configuration['remote']


def test_valid_services_are_loaded(
    valid_service_paths,
    filled_initializer_registry
):
    """Valid service definitions are loaded"""

    registry = runtime.load_services(
        search_path_seq=valid_service_paths,
        init_registry=filled_initializer_registry,
    )

    assert registry.alias['tag']
