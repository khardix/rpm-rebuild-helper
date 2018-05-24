"""Configuration of processing phases"""

from functools import partial

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
