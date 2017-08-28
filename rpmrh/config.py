"""Configuration file processing"""

from functools import partial
from typing import Mapping, Any

import attr
import cerberus
import click
from attr.validators import instance_of
from pytrie import StringTrie

from .service.configuration import InitializerMap, INIT_REGISTRY


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
    },
}


class ConfigurationError(click.ClickException):
    """Invalid configuration values"""

    def __init__(self, message: str, errors):
        super().__init__(message)
        self.errors = errors

    def format_message(self):
        return ''.join([
            super().format_message(),
            ':\n',
            str(self.errors),  # TODO: better formatting
        ])


def _validate_raw_values(config_map: Mapping) -> Mapping:
    """Ensure that the raw configuration map upholds the configuration schema.

    Keyword arguments:
        config_map: The mapping to validate.

    Returns:
        Validated and normalized configuration.

    Raises:
        ConfigurationError: Invalid configuration map.
    """

    validator = cerberus.Validator(schema=SCHEMA)

    if validator.validate(config_map):
        return validator.document

    else:
        message = 'Invalid configuration'
        raise ConfigurationError(message, validator.errors)


def _configure_service(
    config_map: Mapping,
    *,
    registry: InitializerMap = INIT_REGISTRY
):
    """Create a new service instance from its configuration.

    Keyword arguments:
        config_map: The configuration values for a service.
        registry: The initializer registry to use.

    Returns:
        Configured service instance.
    """

    service_type = config_map.pop('type')
    return registry[service_type](**config_map)


@attr.s(slots=True, frozen=True)
class ServiceIndex:
    """Container for fast retrieval of marked/tagged services."""

    #: Service attribute that holds the keys to index by
    key_attribute = attr.ib(validator=instance_of(str))

    #: The indexed services themselves
    container = attr.ib(init=False, default=attr.Factory(StringTrie))

    def insert(self, service: Any) -> None:
        """Index a new service."""

        key_set = getattr(service, self.key_attribute, frozenset())
        for key in key_set:
            self.container[key] = service


@attr.s(slots=True, frozen=True)
class Context:
    """Application configuration context."""

    #: Configured services by tag
    tag_index = attr.ib(
        validator=instance_of(ServiceIndex),
        default=lambda _self: ServiceIndex(key_attribute='tag_prefixes')
    )

    @classmethod
    def from_mapping(
        cls,
        config_map: Mapping,
        *,
        service_registry: InitializerMap = INIT_REGISTRY
    ):
        """Create new Context from raw configuration mapping.

        Keyword arguments:
            config_map: The values to create the instance from.
            service_registry: Initializer registry for the configured services.

        Returns:
            Initialized Context.
        """

        config_map = _validate_raw_values(config_map)
        configure_service = partial(
            _configure_service,
            registry=service_registry
        )

        tag_index = ServiceIndex(key_attribute='tag_prefixes')

        # Instantiate and index the services
        for service in map(configure_service, config_map['services']):
            tag_index.insert(service)

        return cls(tag_index=tag_index)
