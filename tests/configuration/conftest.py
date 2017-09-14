"""Shared fixtures for configuration testing"""

from copy import deepcopy
from types import MappingProxyType

import pytest


class UniversalTestService(dict):
    """Service class for testing purposes.

    - Accepts arbitrary initialization arguments.
    - Provides attribute access to predefined values.
    """

    # Name of this type in initializer registry
    type_name = 'test-service'

    # Valid configuration for this service
    configuration = MappingProxyType({
        'type': type_name,
        'name': 'UniversalTestService',
        'scalar': 42,
        'sequence': list(range(5)),
        'mapping': {'lang': 'en_US'},
    })

    @property
    def tag_prefixes(self):
        return self.get('tag_prefixes', {'test'})


class OtherTestService(dict):
    """Same as UniversalTestService, but different type."""

    type_name = 'other-service'

    configuration = MappingProxyType({
        'type': type_name,
        'name': 'OtherTestService',
    })

    @property
    def other_prefixes(self):
        return self.get('other_prefixes', {'other'})


class UnknownTestService(dict):
    """Service that should not match the tested filters"""

    # Name of this type in initializer registry
    type_name = 'unknown-service'

    # Valid configuration for this service
    configuration = MappingProxyType({
        'type': type_name,
        'name': 'UnknownTestService',
    })

    unknown_prefixes = {'unknown'}


@pytest.fixture
def initializer_registry():
    """Empty initializer registry"""

    return dict()


@pytest.fixture
def service_type():
    """Unregistered service type."""

    return UniversalTestService


@pytest.fixture
def other_type():
    """Different unregistered service type."""

    return OtherTestService


@pytest.fixture
def unknown_type():
    """Type of service not known to any registry"""

    return UnknownTestService


@pytest.fixture
def registered_service_type(service_type, initializer_registry):
    """Registered service type"""

    key = service_type.type_name
    initializer_registry[key] = service_type

    yield service_type

    del initializer_registry[key]


@pytest.fixture
def filled_initializer_registry(service_type, initializer_registry):
    """Registered service type"""

    key = service_type.type_name
    initializer_registry[key] = service_type

    yield initializer_registry

    del initializer_registry[key]


@pytest.fixture
def valid_configuration(service_type):
    """Raw configuration for the test service."""

    configuration = {
        'service': [service_type.configuration.copy()],
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
                'tag_prefixes': {'extra'},
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
def configured_service(service_type):
    """Configured instance of the test service."""

    return service_type(**{
        key: service_type.configuration[key]
        for key in service_type.configuration.keys() - {'type'}
    })
