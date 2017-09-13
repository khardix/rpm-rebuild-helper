"""Configuration context for the whole application"""

from functools import reduce
from typing import Mapping, Sequence

import attr
import cerberus
from attr.validators import instance_of

from .validation import SCHEMA, GroupKind, validate_raw, merge_raw
from ..service.configuration import INIT_REGISTRY, InitializerMap, instantiate
from ..service.configuration import Index, IndexGroup


@attr.s(slots=True)
class Context:
    """Container object for application configuration."""

    #: Indexed service by their key attribute and group name prefix
    service_index = attr.ib(validator=instance_of(IndexGroup))

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
            'service_index': IndexGroup(
                (g.key_attribute, Index()) for g in GroupKind
            ),
            'alias': valid['alias'],
        }

        # Distribute the services
        attributes['service_index'].distribute(*(
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
