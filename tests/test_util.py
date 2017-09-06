"""Tests for the rpmrh.util module"""

from io import BytesIO

import pytest

from rpmrh import util


@pytest.fixture
def mock_package_resources(monkeypatch):
    """Prepared pkg_resources environment."""

    dir_listing = {
        'conf.d': ['a.service.toml', 'b.service', 'c.service.toml'],
        'other': ['fail.service.toml'],
    }

    file_contents = {
        'conf.d/a.service.toml': BytesIO('OK'.encode('utf-8')),
        'conf.d/b.service': BytesIO('FAIL'.encode('utf-8')),
        'conf.d/c.service.toml': BytesIO('OK'.encode('utf-8')),
        'other/fail.service.toml': BytesIO('FAIL'.encode('utf-8')),
    }

    monkeypatch.setattr(
        util, 'resource_listdir',
        lambda __, path: dir_listing[path],
    )
    monkeypatch.setattr(
        util, 'resource_stream',
        lambda __, path: file_contents[path],
    )


@pytest.fixture
def mock_config_files(fs):
    """Mock file system with XDG configuration files."""

    file_contents = {
        '~/.config/rpmrh/user.service.toml': 'OK',
        '~/.config/rpmrh/fail.service': 'FAIL',
        '/etc/xdg/rpmrh/system.service.toml': 'OK',
    }

    for path, content in file_contents.items():
        fs.CreateFile(path, contents=content, encoding='utf-8')


def test_system_import_imports_module():
    """Assert that the system_import imports the correct module"""

    expected = pytest
    imported = util.system_import('pytest')

    assert imported is expected


def test_system_import_imports_attribute():
    """Ensure that the system_import can import attributes"""

    expected = pytest.raises, pytest.fixture
    imported = util.system_import('pytest', 'raises', 'fixture')

    assert all(imp is exp for imp, exp in zip(imported, expected)), imported


def test_system_import_reports_missing_module():
    """Ensure that the system_import reports missing module"""

    with pytest.raises(util.SystemImportError):
        util.system_import('nonexistent_module')


def test_system_import_reports_missing_attribute():
    """Ensure that the system_import reports missing attribute"""

    with pytest.raises(util.SystemImportError):
        util.system_import('pytest', 'raises', 'nonexistent_attribute')


@pytest.mark.usefixtures('mock_package_resources')
def test_load_pkg_resources_opens_correct_files():
    """Only requested resource files are opened."""

    streams = util.open_resource_files(
        root_dir='conf.d',
        extension='.service.toml',
    )

    contents = [s.read() for s in streams]

    assert all(isinstance(content, str) for content in contents)
    assert all(content == 'OK' for content in contents), contents


@pytest.mark.usefixtures('mock_config_files')
def test_load_conf_files_open_correct_files():
    """Only requested configuration files are opened."""

    streams = util.open_config_files(extension='.service.toml')
    contents = [s.read() for s in streams]

    assert all(isinstance(c, str) for c in contents)
    assert all(content == 'OK' for content in contents), contents
