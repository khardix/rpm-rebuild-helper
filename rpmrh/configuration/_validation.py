"""Common validation routines for configuration files"""

from typing import Mapping, Optional

import cerberus
import click


class InvalidConfiguration(click.ClickException):
    """A configuration map did not pass a validity check."""


def validate(
    configuration_map: Mapping, *, schema: Mapping, top_level: Optional[str] = None
) -> dict:
    """Ensure that the configuration mapping conforms to a schema.

    Note:
        This function is a wrapper around cerberus.Validator,
        and its purpose is to hide the non-ergonomic usage of the service
        schema.
        Prefer this to the direct usage of the validator.

    Keyword arguments:
        configuration_map: The contents of the configuration file.
        schema: The schema to validate the configuration_map against.
        top_level: If provided, consider the schema to contain
            extra top-level key. This is a hack to allow for top-level
            usage of key-schema and value-schema.

    Returns:
        Validated and coerced configuration_map.

    Raises:
        InvalidConfiguration: configuration_map did not pass the validation.
    """

    validator = cerberus.Validator(schema=schema)

    # No hack is needed
    if top_level is None:
        if validator.validate(configuration_map):
            return validator.document
        else:
            raise InvalidConfiguration(validator.errors)

    # Wrap document in another dictionary to allow for top-level
    # keyschema and valueschema checks
    else:
        if validator.validate({top_level: configuration_map}):
            return validator.document[top_level]
        else:
            raise InvalidConfiguration(validator.errors[top_level])
