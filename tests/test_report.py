"""Tests for the result serialization format"""
from pathlib import Path
from textwrap import dedent
from typing import Iterable
from typing import Optional

import attr
import pytest
from ruamel import yaml

from rpmrh import report
from rpmrh import rpm

_TEST_PACKAGES = (  # nvr, scl
    ("abcde-1.2.3-1.fc29", None),
    ("rh-python36-2.0-1.el7", "rh-python36"),
    ("rh-python36-python-3.6.3-3.el7", "rh-python36"),
)


@pytest.fixture()
def registry() -> report._SafeTypeConverter:
    """Type registry for test types."""

    return report._SafeTypeConverter()


@pytest.fixture()
def registered_packages(registry) -> Iterable[rpm.PackageLike]:
    """Iterable of packages of registered type"""

    @report.serializable(registry=registry)
    @attr.s(frozen=True, slots=True)
    class Package:
        metadata: rpm.Metadata = attr.ib()
        scl: Optional[rpm.SoftwareCollection] = attr.ib()

        @classmethod
        def to_yaml(cls, representer: yaml.Representer, data: "Package") -> yaml.Node:
            return representer.represent_scalar(
                report._YAMLTag.STRING, "{.metadata.nvr}".format(data)
            )

    return [
        Package(
            metadata=rpm.Metadata.from_nevra(nvr),
            scl=rpm.SoftwareCollection(scl) if scl is not None else None,
        )
        for nvr, scl in _TEST_PACKAGES
    ]


@pytest.fixture()
def filled_container(registered_packages) -> report.Container:
    """Container filled with packages of registered type(s)."""

    result = report.Container()
    for pkg in registered_packages:
        result.insert_package(pkg)
    return result


def test_registry_represents_none(registry):
    """The None value is represented/constructed as expected."""
    node = registry.representer.represent_data(None)
    assert node.value == "~"

    value = registry.constructor.construct_object(node)
    assert value is None


def test_registry_represents_path(registry):
    """The registry can represent and construct path objects."""

    original = Path.cwd()

    node = registry.representer.represent_data(original)
    assert node.value == str(original)

    value = registry.constructor.construct_object(node)
    assert value == original


def test_is_inserted_to_expected_place(registered_packages, filled_container):
    """Any package inserted can be located at expected place"""

    for pkg in registered_packages:
        scl = pkg.scl
        dist = str(pkg.metadata.dist)
        assert pkg in filled_container.result[scl][dist]


def test_container_is_serializable(registry, filled_container):
    """Container with packages is serialized as expected."""

    EXPECTED = dedent(  # WARN: depends on dictionaries being ordered
        """\
        ---
        result:
          ~:
            fc29:
              - abcde-1.2.3-1.fc29
          rh-python36:
            el7:
              - rh-python36-2.0-1.el7
              - rh-python36-python-3.6.3-3.el7
        ...
        """
    )

    assert filled_container.as_yaml(registry=registry) == EXPECTED
