"""Service configuration mechanism.

The registered callables will be used to construct relevant instances
from the application configuration files.
"""

from functools import reduce, partial
from types import MappingProxyType
from typing import Mapping, Callable, Tuple, MutableMapping, Hashable
from typing import Set, Sequence, Container
from typing import Optional, Type, Any, Union, Iterable, Iterator

import attr
import cerberus
from attr.validators import instance_of
from pytrie import StringTrie, Trie

from .validation import SERVICE_SCHEMA, GroupKind, validate_raw, merge_raw
from ..util import iterable

# Type of service initializer table
InitializerMap = MutableMapping[str, Callable]
# Adapted type of dict initializer
IndexGroupInit = Union[Mapping[str, str], Iterable[Tuple[str, str]]]

#: Dispatch table for service initialization
INIT_REGISTRY: InitializerMap = {}


def register(
    name: str,
    initializer: Optional[str] = None,
    *,
    registry: InitializerMap = INIT_REGISTRY
):
    """Enable a type to be used as service in a configuration file.

    Keyword arguments:
        name: The name of the service type in the configuration file.
        initializer: Optional name of a class/static method
            to use instead of __init__.

    Returns:
        Class decorator which registers the passed class.

    Raises:
        KeyError: Duplicate type names within one registry.
        AttributeError: Invalid name of custom initializer.
    """

    if name in registry:
        raise KeyError('Duplicate service type name: {}'.format(name))

    def decorator(cls: Type) -> Type:
        """Insert the initializer into the registry."""

        if not initializer:
            registry[name] = cls
        else:
            registry[name] = getattr(cls, initializer)

        return cls
    return decorator


def instantiate(
    service_conf_map: MutableMapping,
    *,
    registry: InitializerMap = INIT_REGISTRY
) -> Any:
    """Create an instance of registered type from its configuration.

    Keyword arguments:
        service_conf_map: Configuration for the service instance.
        registry: The registry to retrieve the initializer from.

    Returns:
        New instance of configured service.

    Raises:
        KeyError: Configuration does not specify service type.
        KeyError: Unknown service type.
    """

    type_name = service_conf_map.pop('type')
    return registry[type_name](**service_conf_map)


@attr.s(slots=True, frozen=True)
class Index(Mapping):
    """Mapping of group name prefix to matching service instance"""

    #: The name of an indexed object's attribute
    #: which reports the keys to index said object by.
    #:
    #: For example, specify `tag_prefixes`
    #: to index all inserted objects
    #: by all values
    #: in their respective `tag_prefixes` attributes.
    by = attr.ib(validator=instance_of(str))

    #: The container to store the indexed objects in.
    container = attr.ib(
        default=attr.Factory(StringTrie),
        validator=instance_of(Trie),
        hash=False,
    )

    def insert(self, candidate: Any, strict: bool = False):
        """Inserts a candidate to appropriate slots.

        Keyword arguments:
            candidate: The object to insert.
                The object will be accessible by all keys
                reported by attribute with name equal to self.by.
            strict: Whether to raise an AttributeError
                on attempt to insert an object without the right attribute.

        Raises:
            AttributeError: Strict is True and incompatible object should be
                inserted.
        """

        if strict:
            keys = getattr(candidate, self.by)
        else:
            keys = getattr(candidate, self.by, frozenset())

        self.container.update((k, candidate) for k in keys)

    def find(
        self,
        prefix: str,
        *,
        type: Optional[Union[Type, Tuple[Type, ...]]] = None,
        attributes: Optional[Container[str]] = None
    ) -> Any:
        """Find best match for given prefix and parameters.

        Keyword arguments:
            prefix: The base key to look for.
            type: The desired type of the result.
            attributes: The desired attributes of the result.
                All of them must be present on the result object.

        Returns:
            The service fulfilling all the prescribed criteria.

        Raises:
            KeyError: No service fulfilling the criteria has been found.
        """

        # Start from longest prefix
        candidates = reversed(list(self.container.iter_prefix_values(prefix)))

        if type is not None:
            candidates = filter(lambda c: isinstance(c, type), candidates)

        if attributes is not None:
            def has_all_attributes(obj):
                return all(hasattr(obj, a) for a in attributes)
            candidates = filter(has_all_attributes, candidates)

        try:
            return next(candidates)
        except StopIteration:  # convert to appropriate exception type
            message = 'No value with given criteria for {}'.format(prefix)
            raise KeyError(message) from None

    # Mapping interface

    def __getitem__(self, key: Hashable):
        return self.container[key]

    def __iter__(self):
        return iter(self.container)

    def __len__(self):
        return len(self.container)


@attr.s(slots=True, frozen=True)
class Registry:
    """Container object for configured instances."""

    #: Mapping of service kind to index of such services
    index = attr.ib(
        default=attr.Factory(dict),
        validator=instance_of(Mapping),
    )

    #: Mapping of service kind to registered alias map for such services
    alias = attr.ib(
        default=attr.Factory(dict),
        validator=instance_of(Mapping),
    )

    @classmethod
    def from_raw(
        cls,
        raw_configuration: Mapping,
        *,
        known_kinds: Iterable = GroupKind,
        init_registry: InitializerMap = INIT_REGISTRY
    ) -> 'Context':
        """Create new registry from configuration values.

        Keyword arguments:
            raw_configuration: The setting to create the context from.
            init_registry: The registry to use
                for indirect service instantiation.

        Returns:
            Initialized Context.
        """

        valid = validate_raw(raw_configuration)

        # Create registry with no instances
        registry = cls(
            index={k.name: Index(by=k.key_attribute) for k in known_kinds},
            alias=valid['alias'],
        )

        # Create and distribute service instances
        create_instance = partial(instantiate, registry=init_registry)
        service_iter = map(create_instance, valid['services'])
        iterable.consume(registry.distribute(service_iter))

        return registry

    @classmethod
    def from_merged(
        cls,
        *raw_configuration_seq: Sequence[Mapping],
        init_registry: InitializerMap = INIT_REGISTRY
    ) -> 'Context':
        """Create configuration context from multiple configuration mappings.

        Keyword arguments:
            raw_configuration_seq: The configuration values
                to be merged and used for context construction.
            init_registry: The registry to use
                for indirect service instantiation.

        Returns:
            Initialized Context.
        """

        normalized = cerberus.Validator(schema=SERVICE_SCHEMA).normalized

        # Use default values from schema to initialize the accumulator
        accumulator = normalized({})
        norm_sequence = map(normalized, raw_configuration_seq)
        merged = reduce(merge_raw, norm_sequence, accumulator)

        return cls.from_raw(merged, init_registry=init_registry)

    @property
    def all_services(self) -> Set:
        """Quick access to all indexed services."""

        indexed_by_id = {
            id(service): service
            for index in self.index.values()
            for service in index.values()
        }

        return indexed_by_id.values()

    def distribute(self, service_iter: Iterable) -> Iterator:
        """Distribute the services into the appropriate indexes.

        Note that only know (with already existing index) key attributes
        are considered.

        Keyword arguments:
            service_seq: The services to distribute.

        Yields:
            The inserted services.
        """

        for service in service_iter:
            for index in self.index.values():
                index.insert(service)
            yield service

    def unalias(self, kind: str, alias: str, format_map: Mapping) -> str:
        """Resolve a registered alias.

        Keyword arguments:
            kind: The kind of alias to expand.
            alias: The value to expand.
            format_map: Formatting values for alias expansion.

        Returns:
            Expanded alias, if matching definition was found.
            The formatted alias itself, in no matching definition was found.

        Raises:
            KeyError: Unknown alias kind.
            KeyError: Missing formatting keys.
        """

        expanded = self.alias[kind].get(alias, alias)
        return expanded.format_map(format_map)

    def find(
        self,
        kind: str,
        full_prefix: str,
        *args,
        **kwargs
    ):
        """Find a specific kind of service.

        Additional arguments are passed to Index.find().

        Keyword arguments:
            kind: The kind of the service to look for.
            full_prefix: The prefix to look for.
            alias_format_map: The formatting values for alias expansion.

        Returns:
            The same as Index.find().

        Raises:
            KeyError: Specified kind is not known.
            Others: The same as Index.find().
        """

        return self.index[kind].find(full_prefix, *args, **kwargs)

    def resolve(
        self,
        kind: str,
        name_or_alias: str,
        *find_arguments,
        alias_format_map: Mapping = MappingProxyType({}),
        **find_kw_arguments
    ):
        """Resolve an alias and find the associated service for it.

        Keyword arguments:
            kind: The kind of service to look for.
            name_or_alias: The name prefix (or alias) to look for.
            alias_format_map: Formatting values for alias resolution.

            Other arguments are passed to the right Index.find().

        Returns: A pair of:
            1.  Fully resolved group name.
            2.  Service associated with that group.
        """

        name = self.unalias(kind, name_or_alias, alias_format_map)
        service = self.find(kind, name, *find_arguments, **find_kw_arguments)

        return name, service
