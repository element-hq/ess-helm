# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
End-to-end tests for the main migration CLI functionality.
Tests the complete workflow from input to output generation.
"""

import base64
import sys

import pytest
import yaml
from ess_migration_tool import __main__


def test_main_e2e_synapse_only(
    monkeypatch,
    tmp_path,
    synapse_config_with_signing_key,
    synapse_config_with_email_templates,
    synapse_config_with_ca_federation_list,
    synapse_config_without_public_baseurl,
    write_synapse_config,
    capsys,
    helm_validator,
):
    """Test the complete end-to-end migration workflow with Synapse only."""

    # Mock the input function to provide the ingress host when prompted
    def mock_input(prompt):
        if "ingress host" in prompt.lower():
            return "matrix.example.com"
        return ""

    monkeypatch.setattr("builtins.input", mock_input)

    # Write Synapse config without public_baseurl to test prompt functionality
    synapse_config_file = write_synapse_config(
        synapse_config_without_public_baseurl
        | synapse_config_with_signing_key
        | synapse_config_with_email_templates
        | synapse_config_with_ca_federation_list
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

    # Mock user input for database choice (select option 1 - existing database, default)
    side_effect = (n for n in ("",))  # Empty string for default choice (existing database)
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Get captured stderr output (where logging goes)
    captured = capsys.readouterr()
    log_output = captured.err

    # Verify override detection behavior
    # listeners should be filtered out (they serve chart-managed resources)
    assert "'listeners' found in synapse.additional" not in log_output, (
        "Listeners with chart-managed resources should be filtered out, not detected as overrides"
    )
    # signing_key_path should NOT be detected (filtered out)
    assert "'signing_key_path' found in synapse.additional[\"00-imported.yaml\"].config" not in log_output
    # database.args.password should NOT be detected (filtered out as it's a secret)
    assert "'database.args.password' found in synapse.additional[\"00-imported.yaml\"].config" not in log_output

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Validate generated values against Helm templates

    success, message = helm_validator(generated_values)
    assert success, f"Helm template validation failed: {message}"

    # Verify basic structure
    assert "synapse" in generated_values
    assert "serverName" in generated_values
    assert generated_values["serverName"] == "test.example.com"

    # Verify Synapse configuration was migrated and is explicitly enabled
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True, "synapse.enabled should be True"

    # Verify that listeners.yml is absent when only chart-managed listeners exist
    if "additional" in synapse_config:
        additional_config = synapse_config["additional"]
        assert "listeners.yml" not in additional_config, (
            'synapse.additional."listeners.yml" should be absent when only chart-managed listeners exist'
        )

    # Verify all other components are explicitly disabled when only Synapse is configured
    other_components = ["matrixAuthenticationService", "elementWeb", "elementAdmin", "matrixRTC"]
    for component in other_components:
        assert component in generated_values, f"{component} should be present in generated values"
        assert generated_values[component]["enabled"] is False, f"{component}.enabled should be False"

    # Verify ingress host was set from prompt (not from public_baseurl)
    assert "ingress" in synapse_config
    assert "host" in synapse_config["ingress"]
    assert synapse_config["ingress"]["host"] == "matrix.example.com"

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
    monkeypatch,
    tmp_path,
    synapse_config_with_signing_key,
    basic_mas_config_with_keys,
    write_synapse_config,
    write_mas_config,
    capsys,
    helm_validator,
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

    # Mock user input for database choice (select option 1 - existing database, default)
    side_effect = (n for n in ("",))  # Empty string for default choice (existing database)
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Get captured stderr output (where logging goes)
    captured = capsys.readouterr()
    log_output = captured.err

    # Verify override detection behavior for MAS
    # http should be detected as override for MAS
    assert "'http' found in matrixAuthenticationService.additional[\"00-imported.yaml\"].config" in log_output
    # listeners should be filtered out for Synapse (they serve chart-managed resources)
    assert "'listeners' found in synapse.additional" not in log_output, (
        "Listeners with chart-managed resources should be filtered out, not detected as overrides"
    )
    # signing_key_path should NOT be detected (filtered out)
    assert "'signing_key_path' found in synapse.additional[\"00-imported.yaml\"].config" not in log_output
    # database.args.password should NOT be detected (filtered out as it's a secret)
    assert "'database.args.password' found in synapse.additional[\"00-imported.yaml\"].config" not in log_output

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Validate generated values against Helm templates

    success, message = helm_validator(generated_values)
    assert success, f"Helm template validation failed: {message}"

    # Verify Synapse configuration was migrated and is explicitly enabled
    assert "synapse" in generated_values
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True, "synapse.enabled should be True"

    # Verify that listeners.yml is absent when only chart-managed listeners exist
    if "additional" in synapse_config:
        additional_config = synapse_config["additional"]
        assert "listeners.yml" not in additional_config, (
            'synapse.additional."listeners.yml" should be absent when only chart-managed listeners exist'
        )

    # Verify MAS configuration was migrated and is explicitly enabled
    assert "matrixAuthenticationService" in generated_values
    mas_config = generated_values["matrixAuthenticationService"]
    assert mas_config["enabled"] is True, "matrixAuthenticationService.enabled should be True"

    # Verify other components are explicitly disabled when not migrated
    other_components = ["elementWeb", "elementAdmin", "matrixRTC"]
    for component in other_components:
        assert component in generated_values, f"{component} should be present in generated values"
        assert generated_values[component]["enabled"] is False, f"{component}.enabled should be False"

    # Verify MAS secrets were handled (using credential schema)
    assert "synapseSharedSecret" in mas_config

    # Verify synapseSharedSecret uses credential schema
    synapse_shared_secret_config = mas_config["synapseSharedSecret"]
    assert "secret" in synapse_shared_secret_config
    assert synapse_shared_secret_config["secret"] == "imported-matrix-authentication-service"
    assert "secretKey" in synapse_shared_secret_config
    assert synapse_shared_secret_config["secretKey"] == "matrixAuthenticationService.synapseSharedSecret"

    # Verify that listeners.yml is absent when only ESS-managed listeners exist
    # (basic_mas_config_with_keys doesn't have custom listeners)
    assert "additional" in mas_config, "MAS should have additional config"
    assert "listeners.yml" not in mas_config["additional"], (
        'matrixAuthenticationService.additional."listeners.yml" should be absent when only ESS-managed listeners exist'
    )

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
                # 3 original secrets + 2-4 keys (rsa, ecdsaPrime256v1, ecdsaSecp256k1, ecdsaSecp384r1)
                assert 5 <= len(secret_content["data"]) <= 7  # 3 original + 2-4 keys
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
                assert "matrixAuthenticationService.privateKeys.rsa" in secret_content["data"]
                assert "matrixAuthenticationService.privateKeys.ecdsaPrime256v1" in secret_content["data"]
                # Verify keys are not empty and have different content
                rsa_key_data = base64.b64decode(secret_content["data"]["matrixAuthenticationService.privateKeys.rsa"])
                ecdsa_key_data = base64.b64decode(
                    secret_content["data"]["matrixAuthenticationService.privateKeys.ecdsaPrime256v1"]
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


def test_main_e2e_mas_with_custom_listeners(
    monkeypatch,
    tmp_path,
    synapse_config_with_signing_key,
    basic_mas_config_with_keys,
    write_synapse_config,
    write_mas_config,
    capsys,
    helm_validator,
):
    """Test that custom MAS listeners are preserved in additional config."""
    # Add listeners structure to MAS config (it doesn't have one by default)
    mas_config = basic_mas_config_with_keys.copy()
    mas_config["http"]["listeners"] = [
        {
            "name": "web",
            "binds": [{"port": 8080, "host": "0.0.0.0"}],
            "resources": [
                {"name": "human"},
                {"name": "discovery"},
                {"name": "oauth"},
                {"name": "compat"},
                {"name": "assets"},
                {"name": "graphql"},
                {"name": "adminapi"},
            ],
        },
        {
            "name": "internal",
            "binds": [{"port": 8081, "host": "0.0.0.0"}],
            "resources": [{"name": "health"}, {"name": "prometheus"}, {"name": "connection-info"}],
        },
        {
            "name": "custom",
            "binds": [{"port": 9000, "host": "0.0.0.0"}],
            "resources": [{"name": "custom-api"}, {"name": "special-endpoint"}],
        },
    ]

    # Write configuration files
    synapse_config_file = write_synapse_config(synapse_config_with_signing_key)
    mas_config_file = write_mas_config(mas_config)

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

    # Mock user input for database choice (select option 1 - existing database, default)
    side_effect = (n for n in ("",))  # Empty string for default choice (existing database)
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Verify MAS configuration was migrated
    assert "matrixAuthenticationService" in generated_values
    mas_config = generated_values["matrixAuthenticationService"]
    assert mas_config["enabled"] is True

    # Verify that custom listeners are preserved in additional config
    assert "additional" in mas_config, "Additional config should be created for custom listeners"
    additional_config = mas_config["additional"]

    # Verify that listeners.yml is present in the additional config
    assert "listeners.yml" in additional_config, (
        'matrixAuthenticationService.additional."listeners.yml" should be present when custom listeners exist'
    )

    # Verify the content of listeners.yml
    listeners_config_content = yaml.safe_load(additional_config["listeners.yml"]["config"])
    assert "http" in listeners_config_content, "HTTP section should be present in the config"
    assert "listeners" in listeners_config_content["http"], "Listeners should be present in the HTTP config"
    listeners = listeners_config_content["http"]["listeners"]
    assert len(listeners) == 1, "Should have exactly one custom listener"
    assert listeners[0]["name"] == "custom", "Should preserve custom listener name"
    assert listeners[0]["binds"][0]["port"] == 9000, "Should preserve custom listener port"
    assert len(listeners[0]["resources"]) == 2, "Should preserve both custom resources"
    resource_names = [r["name"] for r in listeners[0]["resources"]]
    assert "custom-api" in resource_names, "Should preserve custom-api resource"
    assert "special-endpoint" in resource_names, "Should preserve special-endpoint resource"
    # Verify ESS-managed listeners are NOT present
    assert not any(lstn.get("binds", [{}])[0].get("port") == 8080 for lstn in listeners), (
        "ESS-managed port 8080 should be filtered out"
    )
    assert not any(lstn.get("binds", [{}])[0].get("port") == 8081 for lstn in listeners), (
        "ESS-managed port 8081 should be filtered out"
    )


def test_main_e2e_synapse_existing_database(
    monkeypatch,
    tmp_path,
    synapse_config_with_signing_key,
    write_synapse_config,
    helm_validator,
):
    """Test the complete end-to-end migration workflow with Synapse using existing database."""
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

    # Mock user input for database choice (select option 1 - existing database)
    side_effect = (n for n in ("1",))  # Just database choice, no missing secrets
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    monkeypatch.setattr(sys, "argv", test_args)
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Validate generated values against Helm templates

    success, message = helm_validator(generated_values)
    assert success, f"Helm template validation failed: {message}"

    # Verify Synapse configuration was migrated with existing database settings
    assert "synapse" in generated_values
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True

    # Verify postgres configuration (should have full database details for existing database)
    assert "postgres" in synapse_config
    postgres_config = synapse_config["postgres"]
    assert postgres_config["database"] == "synapse"
    assert postgres_config["user"] == "synapse"
    assert postgres_config["host"] == "postgres"
    assert postgres_config["port"] == 5432

    # Verify that postgres.enabled is NOT set (should use existing database)
    assert "enabled" not in postgres_config


def test_main_e2e_synapse_ess_managed_database(
    monkeypatch,
    tmp_path,
    synapse_config_with_signing_key,
    write_synapse_config,
    helm_validator,
):
    """Test the complete end-to-end migration workflow with Synapse using ESS-managed Postgres."""
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

    # Mock user input for database choice (select option 2 - ESS-managed Postgres)
    side_effect = (n for n in ("2",))  # Just database choice, no missing secrets
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    monkeypatch.setattr(sys, "argv", test_args)
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Validate generated values against Helm templates

    success, message = helm_validator(generated_values)
    assert success, f"Helm template validation failed: {message}"

    # Verify Synapse configuration was migrated with ESS-managed database settings
    assert "synapse" in generated_values
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True

    # Verify postgres configuration (should have minimal settings for ESS-managed Postgres)
    # For ESS-managed Postgres, postgres.enabled should be set at the global level
    assert "postgres" in generated_values
    postgres_config = generated_values["postgres"]

    # For ESS-managed Postgres, we should have postgres.enabled = True at global level
    assert postgres_config.get("enabled") is True

    # Synapse should not have detailed database connection info (host, port, user, etc.)
    synapse_postgres_config = synapse_config.get("postgres", {})
    assert "host" not in synapse_postgres_config
    assert "port" not in synapse_postgres_config
    assert "user" not in synapse_postgres_config
    assert "database" not in synapse_postgres_config


def test_main_e2e_synapse_listeners_with_custom_listeners(
    monkeypatch,
    tmp_path,
    synapse_config_with_custom_listeners,
    synapse_config_with_signing_key,
    write_synapse_config,
    helm_validator,
):
    """Test that custom listeners are preserved in additional config."""
    # Use config with custom listeners that should be preserved
    custom_config = synapse_config_with_custom_listeners.copy()
    custom_config["signing_key_path"] = synapse_config_with_signing_key["signing_key_path"]
    synapse_config_file = write_synapse_config(custom_config)

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

    # Mock user input for database choice (select option 1 - existing database, default)
    side_effect = (n for n in ("",))  # Empty string for default choice (existing database)
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("builtins.input", lambda _: next(side_effect))
    exit_code = __main__.main()

    # Verify successful execution
    assert exit_code == 0

    # Check that output files were created
    values_file = output_dir / "values.yaml"
    assert values_file.exists(), "values.yaml should be created"

    # Load and verify the generated values
    with open(values_file) as f:
        generated_values = yaml.safe_load(f)

    # Validate generated values against Helm templates

    success, message = helm_validator(generated_values)
    assert success, f"Helm template validation failed: {message}"

    # Verify Synapse configuration was migrated
    assert "synapse" in generated_values
    synapse_config = generated_values["synapse"]
    assert synapse_config["enabled"] is True

    # Verify that custom listeners are preserved in additional config
    # The config has custom listeners (custom_api resource) which should be preserved
    assert "additional" in synapse_config, "Additional config should be created for custom listeners"
    additional_config = synapse_config["additional"]

    # Verify that listeners.yml is present in the additional config
    assert "listeners.yml" in additional_config, (
        'synapse.additional."listeners.yml" should be present when custom listeners exist'
    )

    # Verify the content of listeners.yml
    listeners_config_content = yaml.safe_load(additional_config["listeners.yml"]["config"])
    assert "listeners" in listeners_config_content, "Listeners should be present in the config"
    listeners = listeners_config_content["listeners"]
    assert len(listeners) == 1, "Should have exactly one custom listener"
    assert listeners[0]["resources"][0]["names"] == ["custom_api"], "Should preserve custom_api resource"
