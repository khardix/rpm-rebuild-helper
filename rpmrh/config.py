"""Configuration file processing"""

# TODO: Config file schema and validation

from pathlib import Path
from typing import Mapping, Any, TextIO, Sequence

import attr
import cerberus
import click
import toml

from .service import InitializerMap, REGISTRY as SERVICE_REGISTRY


#: Configuration file schema
SCHEMA = {
    'service': {  # list of services
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


@attr.s(slots=True, frozen=True)
class Context:
    """Application configuration context."""

    #: Raw values for validation and further processing
    _raw_config_map = attr.ib()

    @_raw_config_map.validator
    def validate_config_map(self, _attribute: attr.Attribute, value: Mapping):
        """Ensure that the raw config map upholds the configuration schema."""

        validator = cerberus.Validator(schema=SCHEMA)

        if not validator.validate(value):
            message = 'Invalid configuration'
            raise ConfigurationError(message, validator._errors)

def load_source(
    configuration: Mapping,
    *,
    registry: InitializerMap = SERVICE_REGISTRY
) -> Any:
    """Load single source interface from its configuration.

    Keyword arguments:
        configuration: The raw configuration values for the source.
        registry: The type registry to get initializers from.

    Returns:
        New instance of the source interface.
    """

    type_name = configuration.pop('type')
    return registry[type_name](**configuration)


def load_config_file(
    file: TextIO,
    *,
    registry: InitializerMap = SERVICE_REGISTRY
):
    """Load and interpret a single configuration file.

    Keyword arguments:
        file: The open file to read configuration from.
        registry: The type registry to get initializers from.
    """

    configuration = toml.load(file)

    for source in configuration['source']:
        instance = load_source(source, registry=registry)
        instance.register()


def load_configuration(
    path_seq: Sequence[Path],
    *,
    registry: InitializerMap = SERVICE_REGISTRY
):
    """Load configuration from the files in path_seq.

    The sequence represents priority: values from later files will overwrite
    earlier ones, if conflicts arise.

    Keyword arguments:
        path_seq: Paths to configuration files to process.
        registry: The type registry to get initializers from.
    """

    for path in path_seq:
        with path.open(mode='r', encoding='utf-8') as istream:
            load_config_file(istream, registry=registry)
