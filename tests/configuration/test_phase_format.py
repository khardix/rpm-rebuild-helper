"""Tests the definition and validation of phase configuration format"""

import cerberus
import pytest
import toml

from rpmrh.configuration import phase


CONFIGURATION_FILE_CONTENTS = {
    "valid": toml.loads(
        """\
        [initial.repo]
        service = 'cbs'
        tags = ['tag']

        [initial.check]
        service = 'jenkins'
        tests = ['test', 'other test']

        [koji]
        repo = {service = 'koji', tags = ['f27']}
        build = {service = 'cbs', targets = ['sclo{el}-{collection}-rh-candidate']}  # noqa: E501
    """
    ),
    "empty": {},
    "broken": toml.loads(
        """\
        [broken.repo]
        service = 'cbs'
        # missing tags
    """
    ),
}

VALID_CONFIGURATIONS = ["valid", "empty"]
INVALID_CONFIGURATIONS = ["broken"]


@pytest.fixture
def validator():
    """Validator for the phase schema"""

    return cerberus.Validator(schema=phase.SCHEMA)


@pytest.fixture
def service_map():
    """Mapping of existing services"""

    return {"cbs": (), "jenkins": (), "koji": ()}


@pytest.mark.parametrize("config", VALID_CONFIGURATIONS)
def test_valid_file_validates(validator, config):
    """A valid configuration file passes validation"""

    assert validator.validate({"phase": CONFIGURATION_FILE_CONTENTS[config]})


@pytest.mark.parametrize("config", INVALID_CONFIGURATIONS)
def test_invalid_file_fails_validation(validator, config):
    """An invalid file fails the validation"""

    assert not validator({"phase": CONFIGURATION_FILE_CONTENTS[config]})


@pytest.mark.parametrize("config", VALID_CONFIGURATIONS)
def test_validate_returns_on_valid_file(config):
    """A valid file passes through validate()"""

    norm = phase.validate(CONFIGURATION_FILE_CONTENTS[config])
    # roughly same shape
    assert norm.keys() == CONFIGURATION_FILE_CONTENTS[config].keys()


@pytest.mark.parametrize("config", INVALID_CONFIGURATIONS)
def test_validate_raises_on_invalid_file(config):
    """An invalid file does not passes through validate()"""

    with pytest.raises(phase.InvalidConfiguration):
        phase.validate(CONFIGURATION_FILE_CONTENTS[config])


@pytest.mark.parametrize("config", VALID_CONFIGURATIONS)
def test_validate_integrity_returns_on_valid_references(config, service_map):
    """A file with valid references passes through validate_integrity()"""

    phase_map = CONFIGURATION_FILE_CONTENTS[config]
    validated = phase.validate_integrity(phase_map, service_map)
    assert validated == phase_map


@pytest.mark.parametrize("config", ["valid"])
def test_validate_integrity_raises_on_invalid_references(config, service_map):
    """A file with invalid references raises"""

    phase_map = CONFIGURATION_FILE_CONTENTS[config]
    del service_map["koji"]

    with pytest.raises(phase.InvalidConfiguration):
        phase.validate_integrity(phase_map, service_map)
