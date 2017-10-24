"""Raw configuration data validation and normalization."""

from collections import ChainMap
from enum import Enum
from pprint import pformat
from typing import Mapping, MutableMapping

import cerberus
import click


class GroupKind(Enum):
    """Enumeration of recognized package groups"""

    __slots__ = 'name', 'key_attribute'

    TAG = ('tag', 'tag_prefixes')
    TARGET = ('target', 'target_prefixes')

    def __init__(self, name: str, key_attribute: str):
        #: The name of this group
        self.name = name
        #: Name of the key attribute for this group
        self.key_attribute = key_attribute


#: Main configuration file schema
MAIN_CONF_SCHEMA = {
    'remote': {  # remote resources URL mapping
        'type': 'dict',
        'keyschema': {'type': 'string'},
        'valueschema': {'type': 'string'},
    },
}

#: Service file schema
SERVICE_SCHEMA = {
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
        'keyschema': {'allowed': [g.name for g in GroupKind]},
        'valueschema': {
            'type': 'dict',
            'keyschema': {'type': 'string'},
            'valueschema': {'type': 'string'},
        },
        'default_setter': lambda _doc: {
            g.name: ChainMap() for g in GroupKind
        }
    },
}


class ValidationError(click.ClickException):
    """The provided configuration values were not valid"""

    def __init__(self, message: str, errors: Mapping):
        super().__init__(message)
        self.errors = errors

    def format_message(self):
        return '{message}:\n{errors}'.format(
            message=super().format_message(),
            errors=pformat(self.errors, indent=4, compact=False),
        )


# TODO: Rename to 'merge_raw_service' or make more general
def merge_raw(
    accumulator: MutableMapping,
    piece: Mapping,
    *,
    schema: Mapping = SERVICE_SCHEMA
) -> MutableMapping:
    """Merge raw configuration mapping piece into accumulator.

    The merging is performed in-place -- the accumulator will be modified!

    Keyword arguments:
        accumulator: The mapping to merge the configuration into.
        piece: The mapping to merge.
        schema: The schema used for validation.

    Returns:
        Updated accumulator.
    """

    normalized = cerberus.Validator(schema=schema).normalized

    accumulator = normalized(accumulator)
    piece = normalized(piece)

    # Service merging -- append the sequence
    accumulator['services'].extend(piece['services'])

    # Alias merging -- push the dictionaries
    for kind, alias_map in piece['alias'].items():
        accum_kind_map = accumulator['alias'][kind]
        try:  # Use ChainMap, if present
            accum_kind_map.maps.append(alias_map)
        except AttributeError:  # do an update in the right order
            alias_map.update(accum_kind_map)
            accumulator['alias'][kind] = alias_map

    return accumulator


def validate_raw(
    config_map: Mapping,
    *,
    schema: Mapping = SERVICE_SCHEMA
) -> Mapping:
    """Validate raw configuration data format.

    Keyword arguments:
        config_map: The data to validate.

    Returns:
        Validated and normalized data.

    Raises:
        ValidationError: On validation failures.
    """

    validator = cerberus.Validator(schema=schema)

    if validator.validate(config_map):
        return validator.document
    else:
        message = 'Invalid configuration'
        raise ValidationError(message, validator.errors)
