"""Configuration of processing phases"""

from functools import partial
from typing import Any, Mapping

from ._validation import validate, InvalidConfiguration  # noqa: F401

#: Description of a phase
SCHEMA = {
    "phase": {
        "type": "dict",
        "keyschema": {"type": "string", "coerce": str},
        "valueschema": {
            "type": "dict",
            "schema": {
                "repo": {
                    "type": "dict",
                    "schema": {
                        "service": {"type": "string", "required": True},
                        "tags": {
                            "type": "list",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    },
                },
                "build": {
                    "type": "dict",
                    "schema": {
                        "service": {"type": "string", "required": True},
                        "targets": {
                            "type": "list",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    },
                },
                "check": {
                    "type": "dict",
                    "schema": {
                        "service": {"type": "string", "required": True},
                        "tests": {
                            "type": "list",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        },
    }
}


# Configuration file processing
validate = partial(validate, schema=SCHEMA, top_level="phase")


def validate_integrity(
    phase_map: Mapping[str, Mapping], service_map: Mapping[str, Any]
) -> Mapping[str, Mapping]:
    """Make sure that all services referenced by any phase exist.

    Keyword arguments:
        phase_map: The phase map to validate.
        service_map: The service map to validate against.

    Returns: phase_map

    Raises:
        InvalidConfiguration: A referenced service is missing.
    """

    service_name_iter = (
        service["service"]
        for kind_map in phase_map.values()
        for service in kind_map.values()
    )

    for name in service_name_iter:
        if name in service_map:
            continue
        message = 'Referenced service "{name}" is not configured'
        raise InvalidConfiguration(message.format(name=name))
    else:
        return phase_map
