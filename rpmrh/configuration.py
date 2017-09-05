"""Configuration file processing"""

from functools import reduce
from pprint import pformat
from typing import Mapping, MutableMapping, Sequence, Type

import attr
import cerberus
import click
from attr.validators import instance_of

from .service.configuration import INIT_REGISTRY, InitializerMap, instantiate
from .service.configuration import IndexGroup


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
            'tag': 'tag_prefixes',
        })

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
