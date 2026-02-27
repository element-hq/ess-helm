# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: LicenseRef-Element-Commercial

import logging

from scripts.migration.secrets import SecretDiscovery

from ..mas import MASSecretDiscovery


def test_discover_secrets_from_mas_config(basic_mas_config):
    """Test MAS config with PostgreSQL database URI using transformer."""
    mas_config = basic_mas_config.copy()
    # The basic_mas_config already has database.uri with password

    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Should have discovered the password from database URI using transformer
    assert "matrixAuthenticationService.postgres.password" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.postgres.password"].value == "mas_password"
    assert "matrixAuthenticationService.encryptionSecret" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.encryptionSecret"].value == "my_encryption_key"
