"""Test service configuration file format"""

import cerberus
import pytest
import toml

from rpmrh.configuration import service


CONFIGURATION_FILE_CONTENT = {
    "correct": toml.loads(
        """\
        [minimal]
        type = 'minimal_service'

        [elaborate]
        type = 'elaborate_service'
        arbitrary_field = 'arbitrary_value'
    """
    ),
    "empty": {},
    "broken": toml.loads(
        """\
        [missing_type]  # no type field
    """
    ),
}

VALID_CONTENTS = ["correct", "empty"]
INVALID_CONTENTS = ["broken"]


@pytest.fixture
def validator():
    """Validator object for the file format."""

    return cerberus.Validator(schema=service.SCHEMA)


@pytest.mark.parametrize("content", VALID_CONTENTS)
def test_correct_file_validates(validator, content):
    """Correct file contents validates"""

    assert validator.validate({"service": CONFIGURATION_FILE_CONTENT[content]})


@pytest.mark.parametrize("content", INVALID_CONTENTS)
def test_broken_file_fails_validation(validator, content):
    """Broken file content fails validation"""

    assert not validator.validate({"service": CONFIGURATION_FILE_CONTENT[content]})


@pytest.mark.parametrize("content", VALID_CONTENTS)
def test_validate_returns_on_valid_configuration(content):
    """The validate function returns on valid content."""

    result = service.validate(CONFIGURATION_FILE_CONTENT[content])
    # Approximate the same structure
    assert result.keys() == CONFIGURATION_FILE_CONTENT[content].keys()


@pytest.mark.parametrize("content", INVALID_CONTENTS)
def test_validate_raises_on_invalid_configuration(content):
    """The validate function raises on invalid content."""

    with pytest.raises(service.InvalidConfiguration):
        service.validate(CONFIGURATION_FILE_CONTENT[content])
