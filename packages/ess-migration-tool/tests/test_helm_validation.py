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
    # Note: Must include required fields for helm template to succeed
    values = {
        "serverName": "test.example.com",
        "synapse": {
            "ingress": {
                "host": "synapse.test.example.com",
            },
        },
        "elementWeb": {
            "ingress": {
                "host": "element.test.example.com",
            },
        },
        "matrixAuthenticationService": {
            "ingress": {
                "host": "mas.test.example.com",
            },
        },
        "matrixRTC": {
            "ingress": {
                "host": "rtc.test.example.com",
            },
        },
        "elementAdmin": {
            "ingress": {
                "host": "admin.test.example.com",
            },
        },
    }

    success, message = helm_validator(values)

    # Should succeed (or fail with a meaningful error if chart is missing)
    assert success, f"Valid values should pass validation: {message}"


def test_helm_validation_failure_case(helm_validator):
    """Test that invalid values are handled gracefully."""
    # Invalid values structure that should fail validation
    values = {
        "synapse": "invalid_string_value",  # Should be dict
    }

    success, message = helm_validator(values)

    # Should fail (unless chart is missing, in which case it might pass due to early error)
    assert not success
    assert "don't meet the specifications" in message.lower()
