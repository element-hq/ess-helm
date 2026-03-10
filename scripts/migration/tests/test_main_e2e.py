# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
End-to-end tests for the main migration CLI functionality.
Tests the complete workflow from input to output generation.
"""

import base64
import sys
from unittest.mock import patch

import pytest
import yaml

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
            assert len(secret_content["data"]) == 4
            assert base64.b64decode(secret_content["data"]["synapse.macaroon"]) == b"test_macaroon_secret"
            assert (
                base64.b64decode(secret_content["data"]["synapse.registrationSharedSecret"])
                == b"test_registration_secret"
            )
            assert base64.b64decode(secret_content["data"]["synapse.signingKey"]) == b"test_signing_key_content"
            assert base64.b64decode(secret_content["data"]["synapse.postgres.password"]) == b"test"

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


def test_main_e2e_synapse_with_mas(
    tmp_path, synapse_config_with_signing_key, basic_mas_config_with_keys, write_synapse_config, write_mas_config
):
    """Test the complete end-to-end migration workflow with Synapse and MAS."""
    # Write configuration files
    synapse_config_file = write_synapse_config(synapse_config_with_signing_key)
    mas_config_file = write_mas_config(basic_mas_config_with_keys)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Mock sys.argv to simulate CLI arguments
    test_args = [
        "migration",
        "--synapse-config",
        str(synapse_config_file),
        "--mas-config",
        str(mas_config_file),
        "--output-dir",
        str(output_dir),
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

    # Verify Synapse configuration was migrated
    assert "synapse" in generated_values
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True

    # Verify MAS configuration was migrated
    assert "matrixAuthenticationService" in generated_values
    mas_config = generated_values["matrixAuthenticationService"]
    assert mas_config["enabled"] is True

    # Verify MAS secrets were handled (using credential schema)
    assert "synapseSharedSecret" in mas_config

    # Verify synapseSharedSecret uses credential schema
    synapse_shared_secret_config = mas_config["synapseSharedSecret"]
    assert "secret" in synapse_shared_secret_config
    assert synapse_shared_secret_config["secret"] == "imported-matrix-authentication-service"
    assert "secretKey" in synapse_shared_secret_config
    assert synapse_shared_secret_config["secretKey"] == "matrixAuthenticationService.synapseSharedSecret"

    # Check for Secret files (should be created for both Synapse and MAS secrets)
    secret_files = list(output_dir.glob("*secret.yaml"))
    # Should have at least two secret files (one for Synapse, one for MAS)
    assert len(secret_files) >= 2, "Secret files should be created for both Synapse and MAS secrets"

    # Verify the secret file content
    for secret_file in secret_files:
        with open(secret_file) as f:
            secret_content = yaml.safe_load(f)
            assert secret_content["apiVersion"] == "v1"
            assert secret_content["kind"] == "Secret"
            assert "metadata" in secret_content
            assert "name" in secret_content["metadata"]
            assert "data" in secret_content
            if secret_file.name == "imported-synapse-secret.yaml":
                assert len(secret_content["data"]) == 4
                assert base64.b64decode(secret_content["data"]["synapse.macaroon"]) == b"test_macaroon_secret"
                assert (
                    base64.b64decode(secret_content["data"]["synapse.registrationSharedSecret"])
                    == b"test_registration_secret"
                )
                assert base64.b64decode(secret_content["data"]["synapse.signingKey"]) == b"test_signing_key_content"
            elif secret_file.name == "imported-matrix-authentication-service-secret.yaml":
                assert len(secret_content["data"]) == 5  # 3 original + 2 keys
                assert (
                    base64.b64decode(secret_content["data"]["matrixAuthenticationService.synapseSharedSecret"])
                    == b"synapse_shared_secret_abcdef"
                )
                assert (
                    base64.b64decode(secret_content["data"]["matrixAuthenticationService.encryptionSecret"])
                    == b"my_encryption_key"
                )
                assert (
                    base64.b64decode(secret_content["data"]["matrixAuthenticationService.postgres.password"])
                    == b"mas_password"
                )
                # Check that RSA and ECDSA keys were imported
                assert "matrixAuthenticationService.keys.rsa" in secret_content["data"]
                assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in secret_content["data"]
                # Verify keys are not empty and have different content
                rsa_key_data = base64.b64decode(secret_content["data"]["matrixAuthenticationService.keys.rsa"])
                ecdsa_key_data = base64.b64decode(
                    secret_content["data"]["matrixAuthenticationService.keys.ecdsaPrime256v1"]
                )
                assert len(rsa_key_data) > 0
                assert len(ecdsa_key_data) > 0
                assert rsa_key_data != ecdsa_key_data  # Keys should be different
                # Verify key-type-specific headers (PKCS1 format)
                assert b"-----BEGIN RSA PRIVATE KEY-----" in rsa_key_data
                assert b"-----BEGIN EC PRIVATE KEY-----" in ecdsa_key_data
            else:
                pytest.fail(f"Unexpected secret file: {secret_file.name}")
    mas_additional_config = yaml.safe_load(mas_config["additional"]["00-imported.yaml"]["config"])
    assert "keys_dir" not in mas_additional_config["secrets"]
