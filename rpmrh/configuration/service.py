"""Service configuration mechanism.

The registered callables will be used to construct relevant instances
from the application configuration files.
"""

from functools import reduce
from itertools import product
from typing import Mapping, Callable, Tuple, MutableMapping
from typing import Set, Sequence, Container
from typing import Optional, Type, Any, Union, Iterable

import attr
import cerberus
from attr.validators import instance_of
from pytrie import StringTrie

from .validation import SCHEMA, GroupKind, validate_raw, merge_raw

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


class Index(StringTrie):
    """Mapping of group name prefix to matching service instance"""

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
        candidates = reversed(list(self.iter_prefix_values(prefix)))

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


class IndexGroup(dict):
    """Mapping of key attribute name to :py:class:`Index` of matching services.

    A key attribute is an attribute declaring for which groups
    is the service instance responsible,
    usually by providing a set of group name prefixes.
    An example of key attribute is the `Repository.tag_prefixes` attribute.
    """

    @property
    def all_services(self) -> Set:
        """Quick access to all indexed services."""

        indexed_by_id = {
            id(service): service
            for index in self.values()
            for service in index.values()
        }

        return indexed_by_id.values()

    def distribute(self, *service_seq: Sequence) -> Sequence:
        """Distribute the services into the appropriate indexes.

        Note that only know (with already existing index) key attributes
        are considered.

        Keyword arguments:
            service_seq: The services to distribute.

        Returns:
            The sequence passed as parameter.
        """

        for attribute_name, service in product(self.keys(), service_seq):
            for prefix in getattr(service, attribute_name, frozenset()):
                self[attribute_name][prefix] = service

        return service_seq


@attr.s(slots=True)
class InstanceRegistry:
    """Container object for configured instances."""

    #: Indexed service by their key attribute and group name prefix
    index = attr.ib(validator=instance_of(IndexGroup))

    #: Registered alias mapping by its kind
    alias = attr.ib(validator=instance_of(Mapping))

    @classmethod
    def from_raw(
        cls,
        raw_configuration: Mapping,
        *,
        service_registry: InitializerMap = INIT_REGISTRY
    ) -> 'Context':
        """Create new configuration context from raw configuration values.

        Keyword arguments:
            raw_configuration: The setting to create the context from.
            service_registry: The registry to use
                for indirect service instantiation.

        Returns:
            Initialized Context.
        """

        valid = validate_raw(raw_configuration)

        attributes = {
            'index': IndexGroup(
                (g.key_attribute, Index()) for g in GroupKind
            ),
            'alias': valid['alias'],
        }

        # Distribute the services
        attributes['index'].distribute(*(
            instantiate(service_conf, registry=service_registry)
            for service_conf in valid['services']
        ))

        return cls(**attributes)

    @classmethod
    def from_merged(
        cls,
        *raw_configuration_seq: Sequence[Mapping],
        service_registry: InitializerMap = INIT_REGISTRY
    ) -> 'Context':
        """Create configuration context from multiple configuration mappings.

        Keyword arguments:
            raw_configuration_seq: The configuration values
                to be merged and used for context construction.
            service_registry: The registry to use
                for indirect service instantiation.

        Returns:
            Initialized Context.
        """

        normalized = cerberus.Validator(schema=SCHEMA).normalized

        # Use default values from schema to initialize the accumulator
        accumulator = normalized({})
        norm_sequence = map(normalized, raw_configuration_seq)
        merged = reduce(merge_raw, norm_sequence, accumulator)

        return cls.from_raw(merged, service_registry=service_registry)

    def unalias(self, kind: str, alias: str, **format_map: Mapping) -> str:
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
