"""Tests for the configuration mechanism"""

from copy import deepcopy

import pytest

from rpmrh import config, service


@pytest.fixture
def registry():
    """Fresh configuration registry"""

    return dict()


@pytest.fixture
def service_type(registry):
    """Registered service type."""

    # Accepts arbitrary initialization arguments
    # Reports fixed set(s) of interesting propertires
    @service.register('test-service', registry=registry)
    class UniversalTestService(dict):
        tag_prefixes = {'test-tag'}

    return UniversalTestService


@pytest.fixture
def valid_configuration(service_type):
    """Raw configuration for the test service."""

    configuration = {
        'service': [
            {
                'type': 'test-service',
                'scalar': 42,
                'sequence': ['Hello', 'World'],
                'mapping': {'lang': 'en_US'},
            },
        ],
    }

    return configuration


@pytest.fixture
def invalid_configuration(valid_configuration):
    """Raw configuration for the test service."""

    configuration = deepcopy(valid_configuration)
    del configuration['service'][0]['type']
    return configuration


def test_context_validation_ok(valid_configuration):
    """Valid configuration is validated properly."""

    ctx = config.Context(valid_configuration)
    assert ctx._raw_config_map


def test_context_validation_fail(invalid_configuration):
    """Invalid configuration is reported."""

    with pytest.raises(config.ConfigurationError):
        config.Context(invalid_configuration)
