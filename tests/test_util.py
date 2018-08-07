"""Tests for the rpmrh.util module"""

import pytest

from rpmrh import util


def test_system_import_imports_module():
    """Assert that the system_import imports the correct module"""

    expected = pytest
    imported = util.system_import("pytest")

    assert imported is expected


def test_system_import_imports_attribute():
    """Ensure that the system_import can import attributes"""

    expected = pytest.raises, pytest.fixture
    imported = util.system_import("pytest", "raises", "fixture")

    assert all(imp is exp for imp, exp in zip(imported, expected)), imported


def test_system_import_reports_missing_module():
    """Ensure that the system_import reports missing module"""

    with pytest.raises(util.SystemImportError):
        util.system_import("nonexistent_module")


def test_system_import_reports_missing_attribute():
    """Ensure that the system_import reports missing attribute"""

    with pytest.raises(util.SystemImportError):
        util.system_import("pytest", "raises", "nonexistent_attribute")
