# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only
import logging

import pytest
from ess_migration_tool.extra_files import ExtraFilesDiscovery
from ess_migration_tool.models import DiscoveredSecretTracking, GlobalOptions
from ess_migration_tool.secrets import SecretDiscovery, SecretsError
from ess_migration_tool.synapse import SynapseExtraFileDiscovery, SynapseSecretDiscovery


def test_discover_secrets_from_synapse_config(basic_synapse_config):
    """Test discovering secrets from Synapse configuration with existing database."""

    # Start with basic config and add secret file references
    synapse_config = dict(basic_synapse_config)
    synapse_config["macaroon_secret_key"] = "./macaroon_key.txt"
    synapse_config["registration_shared_secret"] = "my_registration_secret"

    # Update database to use direct password for this test
    synapse_config["database"]["args"]["password"] = "dbpassword"

    # Test with existing database mode to ensure PostgreSQL password is discovered
    global_options = GlobalOptions(use_existing_database=True)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # Should have discovered direct values
    assert discovery.discovered_secrets["synapse.postgres.password"].value == "dbpassword"
    missing_secret_keys = {ds.secret_key for ds, _ in discovery.missing_required_secrets}
    assert missing_secret_keys == {"synapse.signingKey"}

    # Test validation (should fail due to missing synapse.signingKey)
    with pytest.raises(SecretsError):
        discovery.validate_required_secrets()


def test_discover_secrets_from_synapse_config_ess_managed(basic_synapse_config):
    """Test discovering secrets from Synapse configuration with ESS-managed database."""

    # Start with basic config and add secret file references
    synapse_config = dict(basic_synapse_config)
    synapse_config["macaroon_secret_key"] = "./macaroon_key.txt"
    synapse_config["registration_shared_secret"] = "my_registration_secret"

    # Update database to use direct password for this test
    synapse_config["database"]["args"]["password"] = "dbpassword"

    # Test with ESS-managed database mode - PostgreSQL password should NOT be discovered
    global_options = GlobalOptions(use_existing_database=False)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # Should NOT have discovered the PostgreSQL password when using ESS-managed database
    assert "synapse.postgres.password" not in discovery.discovered_secrets
    # But should still discover other secrets
    assert discovery.discovered_secrets["synapse.registrationSharedSecret"].value == "my_registration_secret"
    missing_secret_keys = {ds.secret_key for ds, _ in discovery.missing_required_secrets}
    assert missing_secret_keys == {"synapse.signingKey"}

    # Test validation (should fail due to missing synapse.signingKey)
    with pytest.raises(SecretsError):
        discovery.validate_required_secrets()


def test_discover_extra_files_from_synapse_config(tmp_path, synapse_config_with_email_templates):
    """Test discovering extra files from Synapse configuration."""

    # Start with basic config and add secret file references
    synapse_config = dict(synapse_config_with_email_templates)
    discovery = ExtraFilesDiscovery(
        summary_logger=logging.getLogger(),
        secrets_strategy=SynapseSecretDiscovery(GlobalOptions(use_existing_database=True)),
        strategy=SynapseExtraFileDiscovery(),
        source_file="homeserver.yaml",
        global_options=GlobalOptions(),
    )

    discovery.discover_extra_files_from_config(synapse_config)
    assert tmp_path / "email_templates" / "password_reset.html" in discovery.discovered_extra_files
    assert tmp_path / "email_templates" / "registration.html" in discovery.discovered_extra_files
    assert len(discovery.discovered_extra_files) == 2


def test_permission_error_handling_for_secrets(tmp_path, basic_synapse_config):
    """Test that permission errors are handled gracefully for secret files."""
    # Create a restricted signing key file
    restricted_key = tmp_path / "signing.key"
    restricted_key.write_text("restricted_signing_key_content")
    restricted_key.chmod(0o200)  # Write-only for owner

    # Create config with restricted file reference
    synapse_config = dict(basic_synapse_config)
    synapse_config["signing_key_path"] = str(restricted_key)
    synapse_config["database"]["args"]["password"] = "test_password"
    synapse_config["macaroon_secret_key"] = "test_macaroon_key"

    # Test secret discovery
    global_options = GlobalOptions(use_existing_database=True)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # Signing key should be in missing required secrets due to permission error
    missing_secret_keys = {ds.secret_key for ds, _ in discovery.missing_required_secrets}
    assert "synapse.signingKey" in missing_secret_keys

    # Check that the failure information is stored in missing_required_secrets tuple
    signing_key_failures = [
        error_msg for ds, error_msg in discovery.missing_required_secrets if ds.secret_key == "synapse.signingKey"
    ]
    assert len(signing_key_failures) == 1
    assert "Permission denied reading file:" in signing_key_failures[0]
    assert str(restricted_key) in signing_key_failures[0]

    # Other secrets should be discovered normally
    assert "synapse.postgres.password" in discovery.discovered_secrets
    assert "synapse.macaroon" in discovery.discovered_secrets

    # Clean up: restore permissions for cleanup
    restricted_key.chmod(0o644)


def test_discover_appservice_registration_files(tmp_path, basic_synapse_config):
    """Test discovering appservice registration files from Synapse configuration."""
    # Create test appservice registration files
    appservice1 = tmp_path / "appservice1.yaml"
    appservice1.write_text("id: appservice1\nurl: http://localhost:8001\n")

    appservice2 = tmp_path / "appservice2.yaml"
    appservice2.write_text("id: appservice2\nurl: http://localhost:8002\n")

    # Create config with appservice config files
    synapse_config = dict(basic_synapse_config)
    synapse_config["app_service_config_files"] = [str(appservice1), str(appservice2)]
    synapse_config["database"]["args"]["password"] = "test_password"

    # Test secret discovery
    global_options = GlobalOptions(use_existing_database=True)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # Appservice registration files should be discovered
    assert "synapse.appservices.0" in discovery.discovered_secrets
    assert "synapse.appservices.1" in discovery.discovered_secrets
    assert (
        discovery.discovered_secrets["synapse.appservices.0"].value == "id: appservice1\nurl: http://localhost:8001\n"
    )
    assert (
        discovery.discovered_secrets["synapse.appservices.1"].value == "id: appservice2\nurl: http://localhost:8002\n"
    )

    # Appservice secrets should have correct source tracking
    assert discovery.discovered_secrets["synapse.appservices.0"].source_file == "synapse.yaml"
    assert discovery.discovered_secrets["synapse.appservices.0"].config_key == "app_service_config_files.0"
    assert discovery.discovered_secrets["synapse.appservices.1"].config_key == "app_service_config_files.1"


def test_appservice_files_missing(tmp_path, basic_synapse_config):
    """Test handling of missing appservice registration files."""
    # Create config with non-existent appservice config files
    synapse_config = dict(basic_synapse_config)
    synapse_config["app_service_config_files"] = ["/nonexistent/appservice1.yaml", "/nonexistent/appservice2.yaml"]
    synapse_config["database"]["args"]["password"] = "test_password"

    # Test secret discovery
    global_options = GlobalOptions(use_existing_database=True)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # Missing appservice files should be in failed secrets (but optional, so not in missing_required)
    # Since appservice secrets are optional, they won't block migration
    assert "synapse.appservices.0" not in discovery.discovered_secrets
    assert "synapse.appservices.1" not in discovery.discovered_secrets
    # Other required secrets should still be missing
    missing_secret_keys = {ds.secret_key for ds, _ in discovery.missing_required_secrets}
    assert "synapse.signingKey" in missing_secret_keys


def test_appservice_files_empty_list(basic_synapse_config):
    """Test handling of empty app_service_config_files list."""
    # Create config with empty appservice config files list
    synapse_config = dict(basic_synapse_config)
    synapse_config["app_service_config_files"] = []
    synapse_config["database"]["args"]["password"] = "test_password"

    # Test secret discovery
    global_options = GlobalOptions(use_existing_database=True)
    synapse_secrets = SynapseSecretDiscovery(global_options)
    discovery = SecretDiscovery(
        synapse_secrets, logging.getLogger(), "synapse.yaml", global_options, DiscoveredSecretTracking()
    )
    discovery.discover_secrets(synapse_config)

    # No appservice secrets should be discovered
    appservice_secrets = [k for k in discovery.discovered_secrets if "appservices" in k]
    assert len(appservice_secrets) == 0
