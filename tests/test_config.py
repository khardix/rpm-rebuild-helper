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


@pytest.fixture
def configured_service(service_type, valid_configuration, registry):
    """Configured instance of the test service."""

    configuration = deepcopy(valid_configuration['service'][0])
    return config._configure_service(configuration, registry=registry)


@pytest.fixture
def tag_index():
    """Index structure for tag_prefixes."""

    return config.ServiceIndex(key_attribute='tag_prefixes')


@pytest.fixture
def other_index():
    """Index structure for different key attribute than tag_prefixes."""

    return config.ServiceIndex(key_attribute='other_prefixes')


def test_valid_configuration_validates(valid_configuration):
    """Valid configuration passes the validation."""

    assert config._validate_raw_values(valid_configuration)


def test_invalid_configuration_raises(invalid_configuration):
    """Invalid configuration raises ConfigurationError on validation."""

    with pytest.raises(config.ConfigurationError):
        config._validate_raw_values(invalid_configuration)


def test_service_is_configured(service_type, configured_service):
    """Registered service is correctly configured."""

    assert isinstance(configured_service, service_type)
    assert configured_service.keys() == {'scalar', 'sequence', 'mapping'}


def test_relevant_service_is_indexed(configured_service, tag_index):
    """Service with proper attribute is inserted into the index."""

    tag_index.insert(configured_service)

    assert all(
        prefix in tag_index.container
        for prefix in configured_service.tag_prefixes
    )


def test_irrelevant_service_pass_index(configured_service, other_index):
    """Service without the attribute is skipped without an exception."""

    other_index.insert(configured_service)

    assert not any(
        prefix in other_index.container
        for prefix in configured_service.tag_prefixes
    )


def test_contex_is_created_from_sigle_mapping(
    valid_configuration,
    configured_service,
    registry
):
    """Configuration context can be created from a single mapping."""

    print(valid_configuration)

    context = config.Context.from_mapping(
        valid_configuration,
        service_registry=registry,
    )

    assert context
    assert all(
        prefix in context.tag_index.container
        for prefix in configured_service.tag_prefixes
    )
