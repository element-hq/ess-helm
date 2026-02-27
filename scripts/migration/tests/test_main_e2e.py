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


def test_main_e2e_synapse_only(
    tmp_path,
    synapse_config_with_signing_key,
    synapse_config_with_email_templates,
    synapse_config_with_ca_federation_list,
    write_synapse_config,
):
    """Test the complete end-to-end migration workflow with Synapse only."""

    # Write Synapse config
    synapse_config_file = write_synapse_config(
        synapse_config_with_signing_key | synapse_config_with_email_templates | synapse_config_with_ca_federation_list
    )

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
    # Should have one secret file for the discovered secrets
    assert len(secret_files) == 1, "Secret files should be created for discovered secrets"

    # Verify the secret file content
    for secret_file in secret_files:
        with open(secret_file) as f:
            secret_content = yaml.safe_load(f)
            assert secret_content["apiVersion"] == "v1"
            assert secret_content["kind"] == "Secret"
            assert "metadata" in secret_content
            assert "name" in secret_content["metadata"]
            assert "data" in secret_content

    config_maps_files = list(output_dir.glob("*configmap.yaml"))
    # Should have one configmap file for the discovered extra files
    assert len(config_maps_files) == 1, "ConfigMap files should be created for discovered extra files"
    for config_map_file in config_maps_files:
        with open(config_map_file) as f:
            config_map_content = yaml.safe_load(f)
            assert config_map_content["apiVersion"] == "v1"
            assert config_map_content["kind"] == "ConfigMap"
            assert "metadata" in config_map_content
            assert config_map_content["metadata"]["name"] == "imported-synapse"
            assert "data" in config_map_content
            # We expect 2 mail templates to be in the configmap
            assert config_map_content["data"].get("registration.html")
            assert config_map_content["data"].get("password_reset.html")
    assert synapse_config["extraVolumes"] == [
        {
            "name": "imported-synapse",
            "configMap": {
                "name": "imported-synapse",
            },
        },
    ]
    assert synapse_config["extraVolumeMounts"] == [
        {
            "name": "imported-synapse",
            "mountPath": "/etc/synapse/extra/another-ca.pem",
            "subPath": "another-ca.pem",
        },
        {
            "name": "imported-synapse",
            "mountPath": "/etc/synapse/extra/ca-second.pem",
            "subPath": "ca-second.pem",
        },
        {
            "name": "imported-synapse",
            "mountPath": "/etc/synapse/extra/ca1.pem",
            "subPath": "ca1.pem",
        },
        {
            "name": "imported-synapse",
            "mountPath": "/etc/synapse/extra/email_templates/password_reset.html",
            "subPath": "password_reset.html",
        },
        {
            "name": "imported-synapse",
            "mountPath": "/etc/synapse/extra/email_templates/registration.html",
            "subPath": "registration.html",
        },
    ]
    synapse_additional_config = yaml.safe_load(synapse_config["additional"]["00-imported.yaml"]["config"])
    assert synapse_additional_config["templates"]["custom_template_directory"] == "/etc/synapse/extra/email_templates"
    assert synapse_additional_config["federation_custom_ca_list"] == [
        "/etc/synapse/extra/ca1.pem",
        "/etc/synapse/extra/ca-second.pem",
        "/etc/synapse/extra/another-ca.pem",
    ]
