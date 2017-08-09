"""Configuration file processing"""

from typing import Mapping, Callable, Optional, Type

#: Registry of all the types that can be created from configuration
TYPE_REGISTRY: Mapping[str, Callable] = {}


def register_type(
    name: str,
    initializer: Optional[str] = None,
    *,
    registry: Mapping[str, Callable] = TYPE_REGISTRY
) -> Callable:
    """Enable a type to be used as a configured source.

    Each type that should be recognized
    when processing a configuration file
    have to be decorated with this.

    Keyword arguments:
        name: The name of the type within a configuration file.
        initializer: Optional (class-level) callable
            that should be used for creating instances
            and processing the configuration values.
        registry: The mapping to register the type into.

    Returns:
        A decorator that registers the type.
    """

    # No duplicates
    if name in registry:
        raise KeyError('Type {} already registered!'.format(name))

    def decorator(cls: Type) -> Type:
        if not initializer:  # use __init__
            registry[name] = cls
        else:  # use the initializer with bound class argument
            registry[name] = getattr(cls, initializer)

        return cls
    return decorator
