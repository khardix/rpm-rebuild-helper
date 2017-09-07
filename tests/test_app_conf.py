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
        'alias': {
            'tag': {
                'test': 'test-tag-{extra}',
            },
        },
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
        ],

        'alias': {
            'tag': {
                'test': 'hidden',
            },
        },
    }

    return [deepcopy(valid_configuration), extra_configuration]


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


@pytest.fixture
def context(valid_configuration, registry):
    """Filled configuration context."""

    return config.Context(
        deepcopy(valid_configuration),
        service_registry=registry
    )


def test_valid_configuration_validates(valid_configuration):
    """Valid configuration passes the validation."""

    assert config.validate_raw(valid_configuration)


def test_invalid_configuration_raises(invalid_configuration):
    """Invalid configuration raises ConfigurationError on validation."""

    with pytest.raises(config.ConfigurationError):
        config.validate_raw(invalid_configuration)


def test_contex_is_created_from_sigle_mapping(configured_service, context):
    """Configuration context can be created from a single mapping."""

    assert context
    assert all(
        prefix in context.index[config.GroupKind.TAG]
        for prefix in configured_service.tag_prefixes
    )
    assert context.alias[config.GroupKind.TAG]['test'] == 'test-tag-{extra}'


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
    assert len(context.index[config.GroupKind.TAG]) == 2
    assert all(
        tag in context.index[config.GroupKind.TAG]
        for tag in {'test-tag', 'extra'}
    )
    assert context.alias[config.GroupKind.TAG]['test'] == 'test-tag-{extra}'


def test_context_expand_existing_alias(context):
    """Context can expand existing alias."""

    full_name = context.unalias(config.GroupKind.TAG, 'test', extra='world')

    assert full_name == 'test-tag-world'


def test_context_format_missing_alias(context):
    """Unregistered alias is formatted."""

    full_name = context.unalias(
        config.GroupKind.TAG,
        'no-{name}',
        name='tomorrow',
    )

    assert full_name == 'no-tomorrow'


def test_context_fetches_correct_service(context, configured_service):
    """Appropriate service is retrieved"""

    full_name, service = context.group_service(
        kind=config.GroupKind.TAG,
        group_name='test',
        extra='collection',
    )

    assert full_name == 'test-tag-collection'
    assert service == configured_service


def test_context_reports_missing_service(context):
    """Exception is raised on missing service."""

    with pytest.raises(KeyError):
        context.group_service(config.GroupKind.TAG, 'missing')
