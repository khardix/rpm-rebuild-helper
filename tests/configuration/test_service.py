"""Tests for the service configuration mechanism"""

from collections import namedtuple
from functools import reduce
from itertools import starmap

import pytest

from rpmrh.configuration import service


@pytest.fixture
def service_index():
    """Empty service index"""

    return service.Index(by='tag_prefixes')


@pytest.fixture
def filled_service_index(service_type, service_index):
    """Service index with values filled in"""

    configurations = [
        {'tag_prefixes': {'test', 'key'}},
        {'tag_prefixes': {'tes'}},  # Shorter prefix match
    ]

    instances = (service_type(**conf) for conf in configurations)

    for instance in instances:
        service_index.insert(instance)

    return service_index


@pytest.fixture
def instance_registry(valid_configuration, filled_initializer_registry):
    """Configured service.Registry"""

    return service.Registry.from_raw(
        valid_configuration,
        init_registry=filled_initializer_registry,
        known_kinds=list(starmap(
            namedtuple('TestKind', ('name', 'key_attribute')),
            [('tag', 'tag_prefixes'), ('other', 'other_prefixes')],
        )),
    )


@pytest.fixture
def filled_instance_registry(instance_registry, filled_service_index):
    """service.Registry with pre-filled service index."""

    old_index = instance_registry.index.pop('tag')
    instance_registry.index['tag'] = filled_service_index

    yield instance_registry

    instance_registry.index['tag'] = old_index


def test_register_simple(service_type, initializer_registry):
    """Class using __init__ to configure can be registered."""

    decorator = service.register(
        service_type.type_name,
        registry=initializer_registry
    )

    type = decorator(service_type)

    assert type is service_type
    assert initializer_registry[type.type_name] is type


def test_register_custom_initializer(initializer_registry):
    """Class using custom initializer can be registered."""

    @service.register(
        'test', initializer='from_test', registry=initializer_registry
    )
    class Test:
        def __init__(self, identification):
            self.identification = identification

        @classmethod
        def from_test(cls, original):
            return cls(original * 2)

    # Below does not work for some reason
    # assert initializer_registry['test'] is Test.from_test

    instance = initializer_registry['test'](21)
    assert isinstance(instance, Test)
    assert instance.identification == 42


def test_double_registration_fails(initializer_registry):
    """Second registration of class type raises exception"""

    @service.register('test', registry=initializer_registry)
    class A:
        pass

    with pytest.raises(KeyError):
        @service.register('test', registry=initializer_registry)
        class B:
            pass


def test_invalid_initializer_fails(initializer_registry):
    """Non-existent initializer is reported."""

    with pytest.raises(AttributeError):
        @service.register(
            'test', initializer='none', registry=initializer_registry
        )
        class Test:
            pass


def test_instantiate_make_instance(
    registered_service_type, initializer_registry
):
    """Registered type can be instantiated indirectly."""

    instance = service.instantiate(
        registered_service_type.configuration.copy(),
        registry=initializer_registry,
    )

    assert instance
    assert isinstance(instance, registered_service_type)
    assert instance['name'] == 'UniversalTestService'


def test_instantiate_raises_unknown(unknown_type, initializer_registry):
    """Exception is raised on unknown type."""

    with pytest.raises(KeyError):
        service.instantiate(
            unknown_type.configuration.copy(),
            registry=initializer_registry,
        )


def test_index_finds_prefix(filled_service_index):
    """Instance can be found in index by one of its keys."""

    instance = filled_service_index.find('test')

    assert instance
    assert 'test' in instance.tag_prefixes, 'Not longest prefix match'


def test_index_find_raises_on_failure(service_index):
    """An exception is raised when an instance is not found."""

    with pytest.raises(KeyError):
        service_index.find('test')


def test_index_find_filters_by_type(
    service_type,
    unknown_type,
    filled_service_index
):
    """The find function can filter by service type."""

    instance = filled_service_index.find('test', type=service_type)
    assert instance
    assert isinstance(instance, service_type)

    with pytest.raises(KeyError):
        filled_service_index.find('test', type=unknown_type)


@pytest.mark.parametrize('attributes,exception_type', [
    ({'tag_prefixes'}, None),
    ({'tag_prefixes', 'other_attribute'}, KeyError),
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


def test_registry_sorts_correctly(
    service_type, other_type, unknown_type, instance_registry
):
    """IndexGroup sorts the services properly."""

    service, other, unknown = (
        cls(**cls.configuration)
        for cls in (service_type, other_type, unknown_type)
    )

    test_sequence = list(
        instance_registry.distribute((service, other, unknown))
    )

    assert len(test_sequence) == 3

    assert all(
        val is service
        for val in instance_registry.index['tag'].values()
    )
    assert all(
        val is other
        for val in instance_registry.index['other'].values()
    )
    assert all(val is not unknown for val in instance_registry.all_services)


def test_index_group_reports_unique_services(filled_instance_registry):
    """IndexGroup reports all unique indexed services."""

    indexed = filled_instance_registry.all_services

    assert len(indexed) == 2

    prefixes = reduce(lambda acc, p: acc | p.tag_prefixes, indexed, set())
    assert prefixes == {'tes', 'test', 'key'}


def test_instance_registry_is_created_from_sigle_mapping(
    configured_service,
    instance_registry
):
    """service.Registry can be created from a single mapping."""

    assert instance_registry
    assert all(
        prefix in instance_registry.index['tag']
        for prefix in configured_service.tag_prefixes
    )
    assert instance_registry.alias['tag']['test'] == 'test-tag-{extra}'


def test_context_is_created_from_multiple_mappings(
    valid_configuration_seq,
    filled_initializer_registry
):
    """service.Registry can be created from multiple mappings."""

    instance_registry = service.Registry.from_merged(
        *valid_configuration_seq,
        init_registry=filled_initializer_registry,
    )

    assert instance_registry
    assert len(instance_registry.index['tag']) == 2
    assert all(
        tag in instance_registry.index['tag']
        for tag in {'test', 'extra'}
    )
    assert instance_registry.alias['tag']['test'] == 'test-tag-{extra}'


def test_context_expand_existing_alias(instance_registry):
    """Context can expand existing alias."""

    full_name = instance_registry.unalias('tag', 'test', {
        'extra': 'world',
    })

    assert full_name == 'test-tag-world'


def test_context_format_missing_alias(instance_registry):
    """Unregistered alias is formatted."""

    full_name = instance_registry.unalias(
        'tag',
        'no-{name}',
        {
            'name': 'tomorrow',
        },
    )

    assert full_name == 'no-tomorrow'


def test_registry_resolves_group_name(
    instance_registry,
    service_type,
    unknown_type,
):
    """Registry can fully resolve an alias and find associated group."""

    alias = 'test'
    format_map = {'extra': 'world'}

    name, service = instance_registry.resolve(
        kind='tag',
        name_or_alias=alias,
        alias_format_map=format_map,
        type=service_type,
    )

    assert name == 'test-tag-world'
    assert isinstance(service, service_type)
    assert any(name.startswith(prefix) for prefix in service.tag_prefixes)

    with pytest.raises(KeyError):
        instance_registry.resolve(
            kind='tag',
            name_or_alias=alias,
            alias_format_map=format_map,
            type=unknown_type,
        )
