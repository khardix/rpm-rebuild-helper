"""Service configuration mechanism.

The registered callables will be used to construct relevant instances
from the application configuration files.
"""

from itertools import product
from typing import Mapping, Callable, Tuple
from typing import Set, Sequence, Container
from typing import Optional, Type, Any, Union, Iterable

from pytrie import StringTrie

# Type of service initializer table
InitializerMap = Mapping[str, Callable]
# Adapted type of dict initializer
IndexGroupInit = Union[Mapping[str, str], Iterable[Tuple[str, str]]]

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


def instantiate(
    service_conf_map: Mapping,
    *,
    registry: InitializerMap = INIT_REGISTRY
) -> Any:
    """Create an instance of registered type from its configuration.

    Keyword arguments:
        service_conf_map: Configuration for the service instance.
        registry: The registry to retrieve the initializer from.

    Returns:
        New instance of configured service.

    Raises:
        KeyError: Configuration does not specify service type.
        KeyError: Unknown service type.
    """

    type_name = service_conf_map.pop('type')
    return registry[type_name](**service_conf_map)


class Index(StringTrie):
    """Mapping of group name prefix to matching service instance"""

    def find(
        self,
        prefix: str,
        *,
        type: Optional[Union[Type, Tuple[Type, ...]]] = None,
        attributes: Optional[Container[str]] = None
    ) -> Any:
        """Find best match for given prefix and parameters.

        Keyword arguments:
            prefix: The base key to look for.
            type: The desired type of the result.
            attributes: The desired attributes of the result.
                All of them must be present on the result object.

        Returns:
            The service fulfilling all the prescribed criteria.

        Raises:
            KeyError: No service fulfilling the criteria has been found.
        """

        # Start from longest prefix
        candidates = reversed(list(self.iter_prefix_values(prefix)))

        if type is not None:
            candidates = filter(lambda c: isinstance(c, type), candidates)

        if attributes is not None:
            def has_all_attributes(obj):
                return all(hasattr(obj, a) for a in attributes)
            candidates = filter(has_all_attributes, candidates)

        try:
            return next(candidates)
        except StopIteration:  # convert to appropriate exception type
            message = 'No value with given criteria for {}'.format(prefix)
            raise KeyError(message) from None


class IndexGroup(dict):
    """Mapping of key attribute name to :py:class:`Index` of matching services.

    A key attribute is an attribute declaring for which groups
    is the service instance responsible,
    usually by providing a set of group name prefixes.
    An example of key attribute is the `Repository.tag_prefixes` attribute.
    """

    @property
    def all_services(self) -> Set:
        """Quick access to all indexed services."""

        indexed_by_id = {
            id(service): service
            for index in self.values()
            for service in index.values()
        }

        return indexed_by_id.values()

    def distribute(self, *service_seq: Sequence) -> Sequence:
        """Distribute the services into the appropriate indexes.

        Note that only know (with already existing index) key attributes
        are considered.

        Keyword arguments:
            service_seq: The services to distribute.

        Returns:
            The sequence passed as parameter.
        """

        for attribute_name, service in product(self.keys(), service_seq):
            for prefix in getattr(service, attribute_name, frozenset()):
                self[attribute_name][prefix] = service

        return service_seq
