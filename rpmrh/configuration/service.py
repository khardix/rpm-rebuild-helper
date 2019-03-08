"""Registration and configuration of remote services."""
from functools import partial
from typing import Any
from typing import Callable
from typing import Dict
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Type

from ._validation import InvalidConfiguration  # noqa: F401
from ._validation import validate


#: Description of generic service configuration
SCHEMA = {
    "service": {  # dummy key to allow for top-level structure validation
        "type": "dict",
        "keyschema": {"type": "string", "coerce": str},
        "valueschema": {
            "type": "dict",
            "allow_unknown": True,
            "schema": {"type": {"type": "string", "required": True}},
        },
    }
}

#: Registered service types
KNOWN_TYPES: MutableMapping[str, Callable] = {}


class DuplicateError(KeyError):
    """Key already present in a dictionary."""


# Dynamic configuration type registration


def register(
    name: str,
    initializer: Optional[str] = None,
    *,
    registry: MutableMapping = KNOWN_TYPES,
) -> Callable[[Type], Type]:
    """Register an object initializer for service class.

    Keyword arguments:
        name: The name of the registered class within configuration files.
        initializer: Name of the callable to use as initializer value.
            If None, __init__ will be used.
        registry: The mapping to insert the initializer into.

    Returns:
        Decorator for the class to be registered.

    Raises:
        DuplicateError: A type with this name is already registered.
    """

    if name in registry:
        raise DuplicateError(name)

    def decorator(cls: Type) -> Type:
        """Insert the type in the registry."""

        if initializer:
            registry[name] = getattr(cls, initializer)
        else:
            registry[name] = cls

        return cls

    return decorator


def make_instance(configuration_map: Mapping, *, registry: Mapping = KNOWN_TYPES):
    """Turn configuration into proper instance.

    Keyword arguments:
        configuration_map: The configuration for the instance.
        registry: The mapping that contains registered initializers.

    Returns:
        Configured instance.

    Raises:
        KeyError: configuration_map is missing 'type' key.
        KeyError: Requested type is missing from registry.
    """

    configuration_map = dict(configuration_map)
    type_name = configuration_map.pop("type")
    return registry[type_name](**configuration_map)


def make_instance_map(
    service_map: Mapping[str, Mapping], *, registry: MutableMapping = KNOWN_TYPES
) -> Dict[str, Any]:
    """Instantiate all configured services.

    Keyword arguments:
        service_map: The service configuration as raw data.
        registry: The mapping that contains registered initializers.

    Returns: Validated instance dictionary.

    Raises: The same as :func:`make_instance`.
    """

    return {
        name: make_instance(conf, registry=registry)
        for name, conf in service_map.items()
    }


# Configuration file processing
validate = partial(validate, schema=SCHEMA, top_level="service")
