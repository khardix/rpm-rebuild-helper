"""Test the dynamic service registration and instantiation mechanism."""

import pytest

from rpmrh.configuration import service


class Service:
    """Test service"""

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def uppercased(cls, name: str) -> "Service":
        return cls(name.upper())


@pytest.fixture
def type_registry():
    """A dictionary for holding registered services."""

    return {}


def test_register_init(type_registry):
    """Simple register invocation registers the __init__ method"""

    cls = service.register("test", registry=type_registry)(Service)
    assert cls is Service

    obj = type_registry["test"]("name")  # Attempt to invoke Service.__init__
    assert obj.name == "name"


def test_register_other(type_registry):
    """Customized register invocation registers appropriate method"""

    reg = service.register("test", initializer="uppercased", registry=type_registry)
    cls = reg(Service)

    assert cls is Service

    obj = type_registry["test"]("name")
    assert obj.name == "NAME"


def test_register_raises_on_duplicate(type_registry):
    """Register invocation reports attempts to register the same name twice"""

    service.register("test", registry=type_registry)(Service)

    with pytest.raises(service.DuplicateError):
        service.register("test", registry=type_registry)(Service)


def test_instance_can_be_made(type_registry):
    """Instance can be made for registered type"""

    service.register("test", registry=type_registry)(Service)
    obj = service.make_instance(
        {"type": "test", "name": "make"}, registry=type_registry
    )

    assert obj.name == "make"


def test_instance_map_can_be_made(type_registry):
    """Instances can be created from configuration mapping."""

    service.register("test", registry=type_registry)(Service)

    config_map = {
        "foo": {"type": "test", "name": "foo"},
        "bar": {"type": "test", "name": "bar"},
    }

    instance_map = service.make_instance_map(config_map, registry=type_registry)

    assert config_map.keys() == instance_map.keys()
    assert all(isinstance(obj, Service) for obj in instance_map.values())
    assert all(service.name == key for key, service in instance_map.items())
