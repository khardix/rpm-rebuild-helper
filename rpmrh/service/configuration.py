"""Service configuration mechanism.

The registered callables will be used to construct relevant instances
from the application configuration files.
"""

from typing import Mapping, Callable, Optional, Type

# Type of service initializer table
InitializerMap = Mapping[str, Callable]

#: Dispatch table for service initialization
INIT_REGISTRY: InitializerMap = {}


def register(
    name: str,
    initializer: Optional[str] = None,
    *,
    registry: InitializerMap = INIT_REGISTRY
):
    """Enable a type to be used as service in a configuration file.

    Keyword arguments:
        name: The name of the service type in the configuration file.
        initializer: Optional name of a class/static method
            to use instead of __init__.

    Returns:
        Class decorator which registers the passed class.

    Raises:
        KeyError: Duplicate type names within one registry.
        AttributeError: Invalid name of custom initializer.
    """

    if name in registry:
        raise KeyError('Duplicate service type name: {}'.format(name))

    def decorator(cls: Type) -> Type:
        """Insert the initializer into the registry."""

        if not initializer:
            registry[name] = cls
        else:
            registry[name] = getattr(cls, initializer)

        return cls
    return decorator
