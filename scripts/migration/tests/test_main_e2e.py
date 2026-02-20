# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
End-to-end tests for the main migration CLI functionality.
Tests the complete workflow from input to output generation.
"""

import sys
from unittest.mock import patch

import yaml

# Import using the same pattern as other tests
from .. import __main__


def test_main_e2e_synapse_only(tmp_path, synapse_config_with_signing_key, write_synapse_config):
    """Test the complete end-to-end migration workflow with Synapse only."""

    # Write Synapse config
    synapse_config_file = write_synapse_config(synapse_config_with_signing_key)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Mock sys.argv to simulate CLI arguments
    test_args = [
        "migration",
        "--synapse-config",
        str(synapse_config_file),
        "--output-dir",
        str(output_dir),
        "--verbose",
    ]

    # Run the main function with mocked sys.argv
    with patch.object(sys, "argv", test_args):
        exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Verify basic structure
    assert "synapse" in generated_values
    assert "serverName" in generated_values
    assert generated_values["serverName"] == "test.example.com"

    # Verify Synapse configuration was migrated
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True

    # Verify postgres configuration (nested under synapse)
    assert "postgres" in synapse_config
    postgres_config = synapse_config["postgres"]
    assert postgres_config["database"] == "synapse"
    assert postgres_config["user"] == "synapse"
    assert postgres_config["host"] == "postgres"
    assert postgres_config["port"] == 5432

    # Verify secrets were handled (using credential schema)
    for secret in ["macaroon", "registrationSharedSecret", "signingKey"]:
        assert secret in synapse_config
        assert "secret" in synapse_config[secret]
        assert "secretKey" in synapse_config[secret]

    # Check for Secret files (should be created for discovered secrets)
    secret_files = list(output_dir.glob("*secret.yaml"))
    # Should have at least one secret file for the discovered secrets
    assert len(secret_files) > 0, "Secret files should be created for discovered secrets"

    # Verify the secret file content
    for secret_file in secret_files:
        with open(secret_file) as f:
            secret_content = yaml.safe_load(f)
            assert secret_content["apiVersion"] == "v1"
            assert secret_content["kind"] == "Secret"
            assert "metadata" in secret_content
            assert "name" in secret_content["metadata"]
            assert "data" in secret_content
