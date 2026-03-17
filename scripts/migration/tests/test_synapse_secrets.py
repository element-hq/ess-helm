# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only
import logging

import pytest

from ..extra_files import ExtraFilesDiscovery
from ..secrets import SecretDiscovery, SecretsError
from ..synapse import SynapseExtraFileDiscovery, SynapseSecretDiscovery


def test_discover_secrets_from_synapse_config(basic_synapse_config):
    """Test discovering secrets from Synapse configuration."""

    # Start with basic config and add secret file references
    synapse_config = basic_synapse_config.copy()
    synapse_config["macaroon_secret_key"] = "./macaroon_key.txt"
    synapse_config["registration_shared_secret"] = "my_registration_secret"

    # Update database to use direct password for this test
    synapse_config["database"]["args"]["password"] = "dbpassword"

    synapse_secrets = SynapseSecretDiscovery()
    discovery = SecretDiscovery(synapse_secrets, logging.getLogger(), "synapse.yaml")
    discovery.discover_secrets(synapse_config)

    # Should have discovered direct values
    assert discovery.discovered_secrets["synapse.postgres.password"].value == "dbpassword"
    assert set(discovery.missing_required_secrets) == set(["synapse.signingKey"])

    # Test validation (should fail due to missing synapse.signingKey)
    with pytest.raises(SecretsError):
        discovery.validate_required_secrets()


def test_discover_extra_files_from_synapse_config(tmp_path, synapse_config_with_email_templates):
    """Test discovering extra files from Synapse configuration."""

    # Start with basic config and add secret file references
    synapse_config = synapse_config_with_email_templates.copy()
    discovery = ExtraFilesDiscovery(
        pretty_logger=logging.getLogger(),
        secrets_strategy=SynapseSecretDiscovery(),
        strategy=SynapseExtraFileDiscovery(),
        source_file="homeserver.yaml",
    )

    discovery.discover_extra_files_from_config(synapse_config)
    assert tmp_path / "email_templates" / "password_reset.html" in discovery.discovered_extra_files
    assert tmp_path / "email_templates" / "registration.html" in discovery.discovered_extra_files
    assert len(discovery.discovered_extra_files) == 2
