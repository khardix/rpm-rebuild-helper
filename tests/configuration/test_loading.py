"""Tests for configuration loading"""

from collections import namedtuple
from contextlib import ExitStack

import pytest

from rpmrh.configuration import _loading as conf_loading

Resource = namedtuple("Resource", ["name", "content"])


@pytest.mark.usefixtures("mock_package_resources")
def test_load_pkg_resources_opens_correct_files():
    """Only requested resource files are opened."""

    with ExitStack() as to_close:
        stream_iter = conf_loading.open_matching_resources(glob="*.service.toml")
        stream_iter = map(to_close.enter_context, stream_iter)
        resource_list = [Resource(s.name, s.read()) for s in stream_iter]

    # Contents are decoded text
    assert all(isinstance(resource.content, str) for resource in resource_list)
    # Only the correct files are loaded
    assert all(
        resource.content == "SERVICE" for resource in resource_list
    ), resource_list
    # All resources have specified names
    assert all("service.toml" in resource.name for resource in resource_list)


@pytest.mark.usefixtures("mock_config_file_stubs")
def test_load_conf_files_open_correct_files():
    """Only requested configuration files are opened."""

    with ExitStack() as to_close:
        stream_iter = conf_loading.open_matching_files(glob="*.service.toml")
        stream_iter = map(to_close.enter_context, stream_iter)
        file_list = [Resource(s.name, s.read()) for s in stream_iter]

    # All contents are decoded
    assert all(isinstance(f.content, str) for f in file_list)
    # Only the correct files are loaded
    assert all(f.content == "SERVICE" for f in file_list), file_list
    # All files have expected names
    assert all("service.toml" in f.name for f in file_list), file_list


@pytest.mark.parametrize(
    "glob,expected_content", [("*.service.toml", "SERVICE"), ("config.toml", "CONFIG")]
)
@pytest.mark.usefixtures("mock_package_resources", "mock_config_file_stubs")
def test_load_configuration_loads_correct_sources(glob, expected_content):
    """Only requested configuration sources are processed."""

    def interpret(stream):
        return {stream.name: stream.read()}

    conf_map = conf_loading.load_matching_configuration(glob=glob, interpret=interpret)

    # Only correct files are loaded
    assert all(
        value == expected_content for value in conf_map.values()
    ), conf_map.values()
