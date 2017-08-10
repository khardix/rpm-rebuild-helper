"""Tests for the service configuration mechanism"""

import pytest

from rpmrh.service import configuration


@pytest.fixture
def registry():
    """Fresh configuration registry"""

    return dict()


def test_register_simple(registry):
    """Class using __init__ to configure can be registered."""

    @configuration.register('test', registry=registry)
    class Test:
        def __init__(self, identification):
            self.identification = identification

    assert 'test' in registry

    instance = registry['test']('registered')

    assert isinstance(instance, Test)
    assert instance.identification == 'registered'


def test_register_custom_initializer(registry):
    """Class using custom initializer can be registered."""

    @configuration.register('test', initializer='from_test', registry=registry)
    class Test:
        def __init__(self, identification):
            self.identification = identification

        @classmethod
        def from_test(cls, original):
            return cls(original * 2)

    assert 'test' in registry

    instance = registry['test']('reg')

    assert isinstance(instance, Test)
    assert instance.identification == 'regreg'


def test_double_registration_fails(registry):
    """Second registration of class type raises exception"""

    @configuration.register('test', registry=registry)
    class A:
        pass

    with pytest.raises(KeyError):
        @configuration.register('test', registry=registry)
        class B:
            pass


def test_invalid_initializer_fails(registry):
    """Non-existent initializer is reported."""

    with pytest.raises(AttributeError):
        @configuration.register('test', initializer='none', registry=registry)
        class Test:
            pass
