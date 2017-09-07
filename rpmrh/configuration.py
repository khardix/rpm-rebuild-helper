"""Configuration file processing"""

from collections import ChainMap
from enum import Enum
from functools import reduce
from pprint import pformat
from typing import Mapping, MutableMapping, Sequence, Type, Any, Tuple

import attr
import cerberus
import click
from attr.validators import instance_of

from .service.configuration import INIT_REGISTRY, InitializerMap, instantiate
from .service.configuration import IndexGroup


class GroupKind(Enum):
    """Enumeration of recognized package group kinds."""

    TAG = 'tag'


#: Configuration file schema
SCHEMA = {
    'service': {'rename': 'services'},  # allow both singular and plural forms
    'services': {  # list of services
        'type': 'list',
        'schema': {  # single service
            'type': 'dict',
            'schema': {
                'type': {'type': 'string', 'required': True},
            },
            'allow_unknown': True,
        },
        # New list for each normalized dictionary
        'default_setter': lambda _doc: [],
    },

    'alias': {  # registered group name aliases
        'type': 'dict',
        'keyschema': {'allowed': [kind.value for kind in GroupKind]},
        'valueschema': {
            'type': 'dict',
            'keyschema': {'type': 'string'},
            'valueschema': {'type': 'string'},
        },
        'default_setter': lambda _doc: {
            kind.value: ChainMap() for kind in GroupKind
        }
    },
}


class ConfigurationError(click.ClickException):
    """Invalid configuration values"""

    def __init__(self, message: str, errors):
        super().__init__(message)
        self.errors = errors

    def __str__(self):
        return '{cls.__name__}:\n{errors}'.format(
            cls=self.__class__,
            errors=pformat(self.errors),
        )

    def format_message(self):
        return '{super}:\n{errors}'.format(
            super=super().format_message(),
            errors=pformat(self.errors, indent=4),
        )


# Raw configuration data pre-processing

def merge_raw(accumulator: MutableMapping, piece: Mapping) -> MutableMapping:
    """Merge raw configuration mapping piece into accumulator.

    The merging is performed in-place -- the accumulator will be modified!

    Keyword arguments:
        accumulator: The mapping to merge the configuration into.
        piece: The mapping to merge.

    Returns:
        Updated accumulator.
    """

    # Service merging -- append the sequence
    accum_services = accumulator.setdefault('services', [])
    piece_services = piece.get('services', [])
    accum_services.extend(piece_services)

    # Alias merging -- push the dictionaries
    accum_alias = accumulator.setdefault('alias', {})
    for kind, alias_map in piece.get('alias', {}).items():
        accum_alias.setdefault(kind, ChainMap()).maps.append(alias_map)

    return accumulator


def validate_raw(config_map: Mapping) -> Mapping:
    """Validate raw configuration data format.

    Keyword arguments:
        config_map: The data to validate.

    Returns:
        Validated and normalized data.

    Raises:
        ConfigurationError: On validation failures.
    """

    validator = cerberus.Validator(schema=SCHEMA)

    if validator.validate(config_map):
        return validator.document
    else:
        message = 'Invalid configuration'
        raise ConfigurationError(message, validator.errors)


@attr.s(slots=True, init=False)
class Context:
    """Application configuration context."""

    #: Service indexes
    index = attr.ib(init=False, validator=instance_of(IndexGroup))

    #: Registered aliases
    alias = attr.ib(validator=instance_of(Mapping))

    def __init__(
        self,
        raw_config_map: Mapping,
        *,
        service_registry: InitializerMap = INIT_REGISTRY
    ):
        """Initialize the configuration context.

        Keyword attributes:
            raw_config_map: The raw configuration data
                to validate and interpret.
        """

        valid = validate_raw(raw_config_map)

        # Instantiate attributes
        self.index = IndexGroup({
            GroupKind.TAG: 'tag_prefixes',
        })

        self.alias = {
            kind: valid['alias'].get(kind.value, {})
            for kind in GroupKind
        }

        attr.validate(self)

        # Index services
        services = (
            instantiate(service, registry=service_registry)
            for service in valid['services']
        )
        self.index.insert(*services)

    @classmethod
    def from_merged(
        cls: Type['Context'],
        *raw_config_seq: Sequence[Mapping],
        **init_kwargs
    ) -> 'Context':
        """Create configuration context from multiple configuration mappings.

        Keyword arguments:
            raw_config_seq: Sequence of raw configuration mappings,
                in preference order (earlier take precedence over later).
            init_kwargs: Keyword arguments passed to __init__.

        Returns:
            New configuration context.
        """

        validator = cerberus.Validator(schema=SCHEMA)

        # Start accumulator populated with default schema values
        accumulator = validator.normalized({})

        normalized = (validator.normalized(raw) for raw in raw_config_seq)
        merged = reduce(merge_raw, normalized, accumulator)

        return cls(merged, **init_kwargs)

    def unalias(self, kind: GroupKind, alias: str, **format_map) -> str:
        """Expand a registered alias.

        Keyword arguments:
            kind: The kind of alias to expand.
            alias: The alias to expand.
            format_map: Formatting values to be used when expanding.

        Returns:
            If the alias of matching kind is registered,
            returns the expanded version.
            Otherwise, returns the alias with applied formatting.
        """

        full = self.alias[kind].get(alias, alias)
        return full.format_map(format_map)

    def group_service(
        self,
        kind: GroupKind,
        group_name: str,
        **format_map
    ) -> Tuple[str, Any]:
        """Retrieve appropriate service for the requested group.

        Keyword arguments:
            kind: The group kind of the service to retrieve.
            group_name: Name or alias of the group to retrieve service for.
            format_map: Formatting values for alias expansion.

        Returns:
            1. Expanded/unaliased group name.
            2. Service associated with that group.

        Raises:
            KeyError: No service of specified kind
                associated with the group name.
        """

        group = self.unalias(kind, group_name, **format_map)
        service = self.index[kind][group]

        return group, service
