"""Registration and configuration of remote services."""

from typing import Optional, Type
from typing import Callable, Mapping, MutableMapping

import cerberus


#: Description of generic service configuration
SCHEMA = {'service': {  # dummy key to allow for top-level structure validation
    'type': 'dict',
    'keyschema': {'type': 'string', 'coerce': str},
    'valueschema': {'type': 'dict', 'allow_unknown': True, 'schema': {
        'type': {'type': 'string', 'required': True},
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

    if validator.validate({'service': configuration_map}):
        return validator.document['service']
    else:
        raise InvalidConfiguration(validator.errors['service'])
