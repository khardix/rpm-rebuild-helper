"""Tests for the service configuration mechanism"""

from collections import namedtuple

import pytest

from rpmrh.service import configuration


class Registered:
    """Test class for registration"""

    # Name in the registries
    type_name = 'registered'

    def __init__(self, name):
        self.name = name


# configurations for Registered instance
registered_configuration = pytest.mark.parametrize('service_configuration', [
    {'type': Registered.type_name, 'name': 'configured'},
])


# service instances for indexing
Service = namedtuple('Service', ['test_key_set'])
Other = namedtuple('Other', ['other_key_set'])
Unknown = namedtuple('Unknown', ['unknown_key_set'])

service_instances = [
    Service({'test', 'key'}),
    Other({'other', 'set'}),
    Unknown({'unknown'}),
]


@pytest.fixture
def registry():
    """Fresh configuration registry"""

    return dict()


@pytest.fixture
def filled_registry(registry):
    """Configuration registry with expected contents"""

    configuration.register(Registered.type_name, registry=registry)(Registered)

    assert Registered.type_name in registry
    assert registry[Registered.type_name] is Registered

    return registry


@pytest.fixture
def service_index():
    """Empty service index"""

    return configuration.Index()


@pytest.fixture
def filled_service_index(service_index):
    """Service index with values filled in"""

    instances = [
        Service({'test', 'key'}),
        Service({'tes'}),  # Shorter prefix match
    ]

    for instance in instances:
        for key in instance.test_key_set:
            service_index[key] = instance

    return service_index


@pytest.fixture
def service_index_group():
    """Group of empty service indexes"""

    return configuration.IndexGroup(
        test_key_set=configuration.Index(),
        other_key_set=configuration.Index(),
    )


def test_register_simple(filled_registry):
    """Class using __init__ to configure can be registered."""

    instance = filled_registry[Registered.type_name]('test')

    assert isinstance(instance, Registered)
    assert instance.name == 'test'


def test_register_custom_initializer(registry):
    """Class using custom initializer can be registered."""

    @configuration.register('test', initializer='from_test', registry=registry)
    class Test:
        def __init__(self, identification):
            self.identification = identification

        @classmethod
        def from_test(cls, original):
            return cls(original * 2)

    assert 'test' in registry

    instance = registry['test']('reg')

    assert isinstance(instance, Test)
    assert instance.identification == 'regreg'


def test_double_registration_fails(registry):
    """Second registration of class type raises exception"""

    @configuration.register('test', registry=registry)
    class A:
        pass

    with pytest.raises(KeyError):
        @configuration.register('test', registry=registry)
        class B:
            pass


def test_invalid_initializer_fails(registry):
    """Non-existent initializer is reported."""

    with pytest.raises(AttributeError):
        @configuration.register('test', initializer='none', registry=registry)
        class Test:
            pass


@registered_configuration
def test_instantiate_make_instance(service_configuration, filled_registry):
    """Registered type can be instantiated indirectly."""

    instance = configuration.instantiate(
        service_configuration,
        registry=filled_registry,
    )

    assert instance
    assert isinstance(instance, Registered)
    assert instance.name == service_configuration['name']


def test_index_finds_prefix(filled_service_index):
    """Instance can be found in index by one of its keys."""

    instance = filled_service_index.find('test')

    assert instance
    assert 'test' in instance.test_key_set, 'Not longest prefix match'


def test_index_find_raises_on_failure(service_index):
    """An exception is raised when an instance is not found."""

    with pytest.raises(KeyError):
        service_index.find('test')


def test_index_find_filters_by_type(filled_service_index):
    """The find function can filter by service type."""

    instance = filled_service_index.find('test', type=Service)
    assert instance
    assert isinstance(instance, Service)

    with pytest.raises(KeyError):
        filled_service_index.find('test', type=Unknown)


@pytest.mark.parametrize('attributes,exception_type', [
    ({'test_key_set'}, None),
    ({'test_key_set', 'other_attribute'}, KeyError),
])
def test_index_find_filters_by_attributes(
    filled_service_index, attributes, exception_type
):
    """The find function can filter by object attributes."""

    if exception_type is not None:
        with pytest.raises(exception_type):
            filled_service_index.find('test', attributes=attributes)

    else:
        instance = filled_service_index.find('test', attributes=attributes)
        assert instance
        assert all(hasattr(instance, a) for a in attributes)


@registered_configuration
def test_instantiate_raises_unknown(service_configuration, registry):
    """Exception is raised on unknown type."""

    with pytest.raises(KeyError):
        configuration.instantiate(service_configuration, registry=registry)


@pytest.mark.parametrize('service_seq', [service_instances])
def test_index_group_reports_unique_services(service_seq, service_index_group):
    """IndexGroup reports all unique indexed services."""

    test, other, unknown = service_index_group.distribute(*service_seq)
    indexed = service_index_group.all_services

    assert len(indexed) == 2
    assert test in indexed
    assert other in indexed
    assert unknown not in indexed


@pytest.mark.parametrize('service_seq', [service_instances])
def test_index_group_sorts_correctly(service_seq, service_index_group):
    """IndexGroup sorts the services properly."""

    test, other, unknown = service_index_group.distribute(*service_seq)

    assert all(
        val is test
        for val in service_index_group['test_key_set'].values()
    )
    assert all(
        val is other
        for val in service_index_group['other_key_set'].values()
    )
    assert all(val is not unknown for val in service_index_group.all_services)
