"""Configuration test fixtures"""

from io import BytesIO

import pytest

from rpmrh.configuration import _loading as conf_loading


@pytest.fixture
def mock_package_resources(monkeypatch):
    """Prepared pkg_resources environment."""

    dir_listing = {
        "conf.d": ["a.service.toml", "b.service", "c.service.toml"],
        "other": ["fail.service.toml"],
    }

    file_contents = {
        "conf.d/a.service.toml": BytesIO("OK".encode("utf-8")),
        "conf.d/b.service": BytesIO("FAIL".encode("utf-8")),
        "conf.d/c.service.toml": BytesIO("OK".encode("utf-8")),
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


@pytest.fixture
def mock_config_files(fs):
    """Mock file system with XDG configuration files."""

    file_contents = {
        "~/.config/rpmrh/user.service.toml": "OK",
        "~/.config/rpmrh/fail.service": "FAIL",
        "/etc/xdg/rpmrh/system.service.toml": "OK",
    }

    for path, content in file_contents.items():
        fs.CreateFile(path, contents=content, encoding="utf-8")
