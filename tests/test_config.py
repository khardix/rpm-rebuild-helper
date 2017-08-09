"""Tests for the configuration mechanism"""

import pytest

from rpmrh import config


@pytest.fixture
def registry():
    """Fresh configuration registry"""

    return dict()


def test_register_simple(registry):
    """Class using __init__ to configure can be registered."""

    @config.register_type('test', registry=registry)
    class Test:
        def __init__(self, identification):
            self.identification = identification

    assert 'test' in registry

    instance = registry['test']('registered')

    assert isinstance(instance, Test)
    assert instance.identification == 'registered'


def test_register_custom_initializer(registry):
    """Class using custom initializer can be registered."""

    @config.register_type('test', initializer='from_test', registry=registry)
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

    @config.register_type('test', registry=registry)
    class A:
        pass

    with pytest.raises(KeyError):
        @config.register_type('test', registry=registry)
        class B:
            pass
