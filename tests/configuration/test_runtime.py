"""Tests of generic run time configuration handling"""

import pytest
import toml

import pathlib  # This form should by auto-patched by pyfakefs

from rpmrh.configuration import runtime

CONFIGURATION_FILE_CONTENTS = {
    "valid": toml.loads('collection_list_url = "https://example.com/scl-{el}"'),
    "empty": {},
    "invalid": toml.loads("collection_list_url = 42"),
}

VALID_CONFIGURATIONS = ["valid"]
INVALID_CONFIGURATIONS = ["empty", "invalid"]


@pytest.mark.parametrize("conf", VALID_CONFIGURATIONS)
def test_validate_returns_on_valid_file(conf):
    """Valid file passes validation"""

    conf_map = CONFIGURATION_FILE_CONTENTS[conf]
    valid_map = runtime.validate(conf_map)
    assert conf_map == valid_map


@pytest.mark.parametrize("conf", INVALID_CONFIGURATIONS)
def test_validate_raises_on_invalid_file(conf):
    """Invalid file fails validation"""

    conf_map = CONFIGURATION_FILE_CONTENTS[conf]
    with pytest.raises(runtime.InvalidConfiguration):
        runtime.validate(conf_map)


@pytest.mark.usefixtures("mock_config_files")
def test_settings_can_be_loaded_from_configuration_files():
    """A Settings object can be constructed from configuration files"""

    settings = runtime.Settings.from_configuration()

    assert "example.com" in settings.collection_list_url
    assert len(settings.service) == 1 and "test" in settings.service
    assert len(settings.phase) == 1 and "test" in settings.phase


@pytest.mark.usefixtures("mock_config_files")
def test_settings_report_configuration_error():
    "A settings object fails to load invalid configuration" ""

    mangled_path = pathlib.Path("~/.config/rpmrh/test.phase.toml").expanduser()
    with mangled_path.open(mode="a") as file:
        print('unknown_key = "unknown_value"', file=file)

    with pytest.raises(runtime.InvalidConfiguration):
        runtime.Settings.from_configuration()
