"""Service configuration mechanism.

The registered callables will be used to construct relevant instances
from the application configuration files.
"""

from itertools import chain, product
from typing import Mapping, MutableMapping, Callable, Tuple, Sequence, Set
from typing import Optional, Type, Any, Iterator, Union, Iterable

import attr
from attr.validators import instance_of
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


@attr.s(slots=True, frozen=True)
class Index(Mapping):  # add mixin methods
    """Service instance index."""

    # The actual container for the instances
    _container = attr.ib(init=False, default=attr.Factory(StringTrie))

    #: Name of the attribute to index by.
    key_attribute = attr.ib(validator=instance_of(str))

    def insert(self, service: Any) -> Any:
        """Index a service by the matching attribute.

        Keyword arguments:
            service: The service to index.

        Returns:
            The service passed as argument.
        """

        key_set = getattr(service, self.key_attribute, frozenset())
        for key in key_set:
            self._container[key] = service

        return service

    # Mapping interface

    def __getitem__(self, key: str) -> Any:
        """Get item with longest prefix match to a key."""

        return self._container.longest_prefix_value(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the contained keys."""

        return iter(self._container)

    def __len__(self) -> int:
        """Report the size of container."""

        return len(self._container)


@attr.s(slots=True, init=False)
class IndexGroup(MutableMapping):
    """Group of tagged indexes."""

    # Index storage
    _index_map = attr.ib(init=False, default=attr.Factory(dict))

    @property
    def all_services(self) -> Set:
        """Quick access to all indexed services."""

        indexed = chain.from_iterable(
            idx.values() for idx in self._index_map.values()
        )
        id_map = {id(service): service for service in indexed}
        return id_map.values()

    def __init__(
        self,
        initial: Optional[IndexGroupInit] = None,
        **kwargs
    ) -> None:
        """Initialize group of Indexes.

        Interface of this function mimics the interface of dict constructor
        -- see :py:class:`dict` for detailed usage.

        Parameters:
            Generally, an iterable or mapping of index name/tag
            to index attribute key name.
            The values will be processed and turned into proper indexes.
        """

        if initial is None:
            initial = ()
        elif isinstance(initial, Mapping):
            initial = initial.items()

        # Turn values into indexes
        initial = (
            (key, Index(key_attribute=value))
            for key, value in chain(initial, kwargs.items())
        )

        self._index_map = dict(initial)

    def insert(self, *service_seq: Sequence) -> Sequence:
        """Inserts all services to matching indexes.

        Keyword arguments:
            service_seq: The services to insert.

        Returns:
            The sequence passed as parameter.
        """

        for service, index in product(service_seq, self._index_map.values()):
            index.insert(service)

        return service_seq

    # MutableMapping interface

    def __getitem__(self, key):
        """Get matching index."""

        return self._index_map[key]

    def __setitem__(self, key, value):
        """Transform the value into and index, if necessary."""

        if not isinstance(value, Index):
            value = Index(key_attribute=value)

        self._index_map[key] = value

    def __delitem__(self, key):
        """Drop the matching index."""

        del self._index_map[key]

    def __iter__(self):
        """Iterate over the indexes."""

        return iter(self._index_map)

    def __len__(self):
        """Report the number of indexes."""

        return len(self._index_map)
