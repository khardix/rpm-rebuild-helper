"""Configuration test fixtures"""

from io import BytesIO
from os import path
from textwrap import dedent

import pytest
from pyfakefs.fake_pathlib import FakePathlibModule
from xdg.BaseDirectory import xdg_config_home

from rpmrh import RESOURCE_ID
from rpmrh.configuration import _loading as conf_loading


@pytest.fixture
def mock_package_resources(monkeypatch):
    """Prepared pkg_resources environment."""

    dir_listing = {
        "conf.d": ["a.service.toml", "b.service", "c.service.toml"],
        "other": ["fail.service.toml"],
    }

    file_contents = {
        "conf.d/a.service.toml": BytesIO("SERVICE".encode("utf-8")),
        "conf.d/b.service": BytesIO("FAIL".encode("utf-8")),
        "conf.d/c.service.toml": BytesIO("SERVICE".encode("utf-8")),
        "other/fail.service.toml": BytesIO("FAIL".encode("utf-8")),
    }
    # Set names of the IO streams
    for name, stream in file_contents.items():
        stream.name = name

    monkeypatch.setattr(
        conf_loading, "resource_listdir", lambda __, path: dir_listing[path]
    )
    monkeypatch.setattr(
        conf_loading, "resource_stream", lambda __, path: file_contents[path]
    )


@pytest.fixture(autouse=True)
def monkeypatch_pathlib_import(monkeypatch, fs):
    """Patch pathlib.Path imports"""

    fake_pathlib = FakePathlibModule(fs)

    class PathMock:
        def __init__(self, *args, **kwargs):
            self.__delegate = fake_pathlib.Path(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.__delegate, name)

    monkeypatch.setattr(conf_loading, "Path", PathMock)


@pytest.fixture
def mock_xdg_config_home(fs):
    """Mocked XDG configuration environment.

    Yields: Value of :env:`XDG_CONFIG_HOME`.
    """

    fs.create_dir(xdg_config_home)
    yield xdg_config_home


@pytest.fixture
def mock_config_file_stubs(mock_xdg_config_home, fs):
    """Mock file system with XDG configuration files."""

    file_contents = {
        path.join(mock_xdg_config_home, RESOURCE_ID, "user.service.toml"): "SERVICE",
        path.join(mock_xdg_config_home, RESOURCE_ID, "fail.service"): "FAIL",
        path.join(mock_xdg_config_home, RESOURCE_ID, "config.toml"): "CONFIG",
        path.join("/etc/xdg", RESOURCE_ID, "system.service.toml"): "SERVICE",
    }

    for pth, content in file_contents.items():
        fs.create_file(pth, contents=content, encoding="utf-8")


@pytest.fixture
def mock_config_files(mock_xdg_config_home, fs, monkeypatch):
    """Complete valid package configuration"""

    # Disable pkg_resources
    monkeypatch.setattr(conf_loading, "resource_listdir", lambda *__: [])
    monkeypatch.setattr(conf_loading, "resource_stream", lambda *__: BytesIO())

    # Create fake files -- single valid file of each kind
    runtime_path = path.join(mock_xdg_config_home, RESOURCE_ID, "config.toml")
    service_path = path.join(mock_xdg_config_home, RESOURCE_ID, "test.service.toml")
    phase_path = path.join(mock_xdg_config_home, RESOURCE_ID, "test.phase.toml")
    content_map = {
        runtime_path: 'collection_list_url = "https://example.com/scl-{el}"',
        service_path: dedent(
            """\
                [test]
                type = "dnf"
                repo_configs = []
                """
        ),
        phase_path: dedent(
            """\
                [test.repo]
                service = "test"
                tags = []
                """
        ),
    }

    for pth, content in content_map.items():
        fs.create_file(pth, contents=content, encoding="utf-8")

    # Map temporary directory for DNF
    fs.add_real_directory("/var/tmp", read_only=False)
