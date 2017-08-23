"""Configuration file processing"""

from typing import Mapping

import attr
import cerberus
import click


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
