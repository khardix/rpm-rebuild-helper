"""Tests for the CLI tooling."""

import pytest

import rpmrh.cli.tooling as tooling
from rpmrh import rpm


@pytest.fixture
def package_stream():
    """Prepared package stream"""

    metadata = [
        rpm.Metadata(name='test', version='2.1', release='3.el7'),
        rpm.Metadata(name='abcde', version='1.0', release='1.el7'),
        rpm.Metadata(name='abcde', version='2.0', release='1.el7'),
    ]

    return tooling.PackageStream(
        tooling.Package(collection='test', el=7, metadata=m)
        for m in metadata
    )


def test_stream_iteration(package_stream):
    """The iteration is performed in the expected order."""

    assert list(package_stream) == sorted(package_stream._container)


def test_stream_consumption(package_stream):
    """Package stream can be (re-)created by consuming an iterator."""

    iterator = iter(package_stream)
    result = tooling.PackageStream.consume(iterator)

    assert result is not package_stream
    assert result == package_stream
