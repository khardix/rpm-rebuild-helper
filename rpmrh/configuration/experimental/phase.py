"""Configuration of processing phases"""

from typing import Mapping

import cerberus


#: Description of a phase
SCHEMA = {'phase': {
    'type': 'dict',
    'keyschema': {'type': 'string', 'coerce': str},
    'valueschema': {'type': 'dict', 'schema': {
        'repo': {'type': 'list', 'schema': {'type': 'dict', 'schema': {
            'service': {'type': 'string', 'required': True},
            'tags': {
                'type': 'list', 'required': True, 'schema': {'type': 'string'},
            },
        }}},
        'build': {'type': 'list', 'schema': {'type': 'dict', 'schema': {
            'service': {'type': 'string', 'required': True},
            'targets': {
                'type': 'list', 'required': True, 'schema': {'type': 'string'},
            },
        }}},
        'check': {'type': 'list', 'schema': {'type': 'dict', 'schema': {
            'service': {'type': 'string', 'required': True},
            'tests': {
                'type': 'list', 'required': True, 'schema': {'type': 'string'},
            },
        }}},
    }},
}}


class InvalidConfiguration(Exception):
    """The service configuration is not valid."""


# Configuration file processing

def validate(
    configuration_map: Mapping,
    *,
    validator: cerberus.Validator = None,
) -> dict:
    """Ensure that the configuration mapping conforms to the service schema.

    Note:
        This function is a wrapper around cerberus.Validator,
        and its purpose is to hide the non-ergonomic usage of the service
        schema.
        Prefer this to the direct usage of the validator.

    Keyword arguments:
        configuration_map: The contents of the configuration file.
        validator: The validator to use. If None, a new one will be provided.

    Returns:
        Validated and coerced configuration_map.

    Raises:
        InvalidConfiguration: configuration_map did not pass the validation.
    """

    if validator is None:
        validator = cerberus.Validator(schema=SCHEMA)

    if validator.validate({'phase': configuration_map}):
        return validator.document['phase']
    else:
        raise InvalidConfiguration(validator.errors['phase'])
