# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: LicenseRef-Element-Commercial

import logging

from scripts.migration.secrets import SecretDiscovery

from ..mas import MASSecretDiscovery


def test_discover_secrets_from_mas_config(basic_mas_config):
    """Test MAS config with PostgreSQL database URI using transformer."""
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(basic_mas_config)

    # Should have discovered the password from database URI using transformer
    assert "matrixAuthenticationService.postgres.password" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.postgres.password"].value == "mas_password"
    assert "matrixAuthenticationService.encryptionSecret" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.encryptionSecret"].value == "my_encryption_key"


def test_discover_keys_from_mas_config(mas_config_with_keys):
    """Test MAS config with PostgreSQL database URI using transformer."""
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config_with_keys)

    # Should have discovered the password from database URI using transformer
    assert "matrixAuthenticationService.postgres.password" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.postgres.password"].value == "mas_password"
    assert "matrixAuthenticationService.privateKeys.rsa" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.privateKeys.rsa"].value == "test_rsa_content"
    assert "matrixAuthenticationService.privateKeys.ecdsaPrime256v1" in discovery.discovered_secrets
    assert (
        discovery.discovered_secrets["matrixAuthenticationService.privateKeys.ecdsaPrime256v1"].value
        == "prime256v1_key_value"
    )
