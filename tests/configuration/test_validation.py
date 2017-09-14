"""Tests for the configuration mechanism"""

import pytest

from rpmrh.configuration import validation


def test_valid_configuration_validates(valid_configuration):
    """Valid configuration passes the validation."""

    assert validation.validate_raw(valid_configuration)


def test_invalid_configuration_raises(invalid_configuration):
    """Invalid configuration raises ValidationError on validation."""

    with pytest.raises(validation.ValidationError):
        validation.validate_raw(invalid_configuration)


def test_merged_valid_configurations_are_valid(valid_configuration_seq):
    """Multiple valid configurations are merged into valid one."""

    merged = validation.merge_raw(*valid_configuration_seq[:2])
    assert validation.validate_raw(merged)


def test_merged_invalid_configuration_is_invalid(
    valid_configuration_seq, invalid_configuration
):
    """Invalid configuration in merging results in invalid merged one."""

    merged = validation.merge_raw(
        valid_configuration_seq[-1],
        invalid_configuration,
    )

    print(merged)

    with pytest.raises(validation.ValidationError):
        validation.validate_raw(merged)
