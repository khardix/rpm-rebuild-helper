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
service_instances = [
    namedtuple('Test', ['test_key_set'])({'test', 'key'}),
    namedtuple('Other', ['other_key_set'])({'other', 'set'}),
    namedtuple('Unknown', ['unknown_key_set'])({'unknown'}),
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

    return configuration.Index('test_key_set')


@pytest.fixture
def service_index_group():
    """Group of empty service indexes"""

    return configuration.IndexGroup({
        'test': 'test_key_set',
        'other': 'other_key_set',
    })


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


@registered_configuration
def test_instantiate_raises_unknown(service_configuration, registry):
    """Exception is raised on unknown type."""

    with pytest.raises(KeyError):
        configuration.instantiate(service_configuration, registry=registry)


@pytest.mark.parametrize('matching', service_instances[0:1])
def test_index_inserts_matched(matching, service_index):
    """Matching service is indexed."""

    inserted = service_index.insert(matching)

    assert inserted is matching
    assert all(key in service_index for key in matching.test_key_set)
    assert service_index[matching.test_key_set.pop()] is matching


@pytest.mark.parametrize('other', service_instances[1:2])
def test_index_pass_unmatched(other, service_index):
    """Mismatching service is passed without exception."""

    passed = service_index.insert(other)

    assert passed is other
    assert all(key not in service_index for key in other.other_key_set)


@pytest.mark.parametrize('service_seq', [service_instances])
def test_index_group_reports_unique_services(service_seq, service_index_group):
    """IndexGroup reports all unique indexed services."""

    test, other, unknown = service_index_group.insert(*service_seq)
    indexed = service_index_group.all_services

    assert len(indexed) == 2
    assert test in indexed
    assert other in indexed
    assert unknown not in indexed


@pytest.mark.parametrize('service_seq', [service_instances])
def test_index_group_sorts_correctly(service_seq, service_index_group):
    """IndexGroup sorts the services properly."""

    test, other, unknown = service_index_group.insert(*service_seq)

    assert all(val is test for val in service_index_group['test'].values())
    assert all(val is other for val in service_index_group['other'].values())
    assert all(val is not unknown for val in service_index_group.all_services)
