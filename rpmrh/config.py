"""Configuration file processing"""

# TODO: Config file schema and validation

from pathlib import Path
from typing import Mapping, Callable, Optional, Type, Any, TextIO, Sequence

import toml

# Expected type of the type registry
TypeRegistry = Mapping[str, Callable]

#: Registry of all the types that can be created from configuration
KNOWN_TYPES: TypeRegistry = {}


def register_type(
    name: str,
    initializer: Optional[str] = None,
    *,
    registry: TypeRegistry = KNOWN_TYPES
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


def load_source(
    configuration: Mapping,
    *,
    registry: TypeRegistry = KNOWN_TYPES
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


def load_config_file(file: TextIO, *, registry: TypeRegistry = KNOWN_TYPES):
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
    registry: TypeRegistry = KNOWN_TYPES
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
