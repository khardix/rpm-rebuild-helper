"""Tests for the configuration mechanism"""

from copy import deepcopy

import pytest

from rpmrh import configuration as config, service


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
        @property
        def tag_prefixes(self):
            return self.get('tags', {'test-tag'})

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
def valid_configuration_seq(valid_configuration):
    """Sequence of raw configurations for the test service."""

    extra_configuration = {
        'services': [
            {
                'type': 'test-service',
                'name': 'extra-service',
                'tags': {'extra'},
            },
        ]
    }

    return [valid_configuration, extra_configuration]


@pytest.fixture
def invalid_configuration(valid_configuration):
    """Raw configuration for the test service."""

    configuration = deepcopy(valid_configuration)
    del configuration['service'][0]['type']
    return configuration


@pytest.fixture
def configured_service(service_type, valid_configuration, registry):
    """Configured instance of the test service."""

    configuration = deepcopy(valid_configuration['service'][0])
    return service.instantiate(configuration, registry=registry)


def test_valid_configuration_validates(valid_configuration):
    """Valid configuration passes the validation."""

    assert config.validate_raw(valid_configuration)


def test_invalid_configuration_raises(invalid_configuration):
    """Invalid configuration raises ConfigurationError on validation."""

    with pytest.raises(config.ConfigurationError):
        config.validate_raw(invalid_configuration)


def test_contex_is_created_from_sigle_mapping(
    valid_configuration,
    configured_service,
    registry
):
    """Configuration context can be created from a single mapping."""

    print('Valid configuration:', valid_configuration)

    context = config.Context(
        valid_configuration,
        service_registry=registry,
    )

    assert context
    assert all(
        prefix in context.index['tag']
        for prefix in configured_service.tag_prefixes
    )


def test_context_is_created_from_multiple_mappings(
    valid_configuration_seq,
    registry
):
    """Configuration can be created from multiple mappings."""

    context = config.Context.from_merged(
        *valid_configuration_seq,
        service_registry=registry,
    )

    assert context
    assert len(context.index['tag']) == 2
    assert all(tag in context.index['tag'] for tag in {'test-tag', 'extra'})
