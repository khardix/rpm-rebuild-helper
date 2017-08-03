"""Test for the generic service interfaces."""

import pytest

from rpmrh.service import abc


@pytest.fixture
def repository():
    """Provide Repository with an empty registry"""

    yield abc.Repository

    abc.Repository.registry.clear()


@pytest.fixture
def repository_subclass(repository):
    """Provide a fresh subclass object for abc.Repository."""

    class Test(abc.Repository):

        def latest_builds(*_, **__):
            return iter([])

        def download(*_, **__):
            return None

    return Test


def test_repository_registration(repository, repository_subclass):
    """An instance of Repository subclass is registered on initialization."""

    instance = repository_subclass(tag_prefixes={'test'})

    assert repository.registry['test'] is instance
    assert (
        repository.registry.longest_prefix_value('test-el7-build')
        is instance
    )
