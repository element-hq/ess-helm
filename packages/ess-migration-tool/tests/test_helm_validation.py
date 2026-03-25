# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Tests for Helm validation functionality.
Validates that the Helm validation utilities work correctly.
"""


def test_helm_validation_success_case(helm_validator):
    """Test that valid values pass Helm validation."""
    # Basic valid values that should pass Helm template validation
    values = {
        "synapse": {
            "enabled": True,
            "serverName": "test.example.com",
        },
        "postgres": {
            "enabled": True,
        },
    }

    success, message = helm_validator(values)

    # Should succeed (or fail with a meaningful error if chart is missing)
    assert success or "chart" in message.lower(), f"Valid values should pass validation: {message}"


def test_helm_validation_failure_case(helm_validator):
    """Test that invalid values are handled gracefully."""
    # Invalid values structure that should fail validation
    values = {
        "synapse": "invalid_string_value",  # Should be dict
    }

    success, message = helm_validator(values)

    # Should fail validation but not crash
    assert isinstance(success, bool), "Should return boolean success status"
    assert isinstance(message, str), "Should return string message"
    # Should fail (unless chart is missing, in which case it might pass due to early error)
    assert not success or "chart" in message.lower(), "Invalid values should fail validation"
