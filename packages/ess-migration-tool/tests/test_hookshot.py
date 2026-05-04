# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Hookshot migration."""

import logging

from ess_migration_tool.hookshot import (
    HOOKSHOT_STRATEGY_NAME,
    HookshotExtraFileDiscovery,
    HookshotMigration,
    HookshotSecretDiscovery,
)
from ess_migration_tool.migration import ConfigValueTransformer
from ess_migration_tool.models import GlobalOptions


def test_hookshot_strategy_name():
    """Test that Hookshot strategy has correct name."""
    migration = HookshotMigration(GlobalOptions())
    assert migration.name == HOOKSHOT_STRATEGY_NAME


def test_hookshot_enabled_transformation():
    """Test that Hookshot component is enabled."""
    transformer = ConfigValueTransformer(logging.getLogger(), ess_config={})
    migration = HookshotMigration(GlobalOptions())

    config = {"bridge": {"domain": "test.example.com"}}
    transformer.transform_from_config(config, migration.transformations)

    assert transformer.ess_config["hookshot"]["enabled"] is True


def test_bridge_domain_to_server_name():
    """Test that bridge.domain is mapped to global serverName."""
    transformer = ConfigValueTransformer(logging.getLogger(), ess_config={})
    migration = HookshotMigration(GlobalOptions())

    config = {"bridge": {"domain": "test.example.com"}}
    transformer.transform_from_config(config, migration.transformations)

    assert transformer.ess_config["serverName"] == "test.example.com"


def test_bridge_url_to_synapse_ingress_host():
    """Test that bridge.url is mapped to synapse.ingress.host."""
    transformer = ConfigValueTransformer(logging.getLogger(), ess_config={})
    migration = HookshotMigration(GlobalOptions())

    config = {"bridge": {"domain": "test.example.com", "url": "http://synapse:8008"}}
    transformer.transform_from_config(config, migration.transformations)

    assert transformer.ess_config["synapse"]["ingress"]["host"] == "synapse"


def test_secret_discovery_schema():
    """Test that Hookshot has correct ESS secret schema for passFile."""
    secret_discovery = HookshotSecretDiscovery(GlobalOptions())
    schema = secret_discovery.ess_secret_schema

    assert "hookshot.passkey" in schema
    assert schema["hookshot.passkey"].config_path == "passFile"


def test_extra_file_discovery_ignored_keys():
    """Test that passFile and encryption.storagePath are ignored for extra files."""
    extra_files = HookshotExtraFileDiscovery()
    assert "passFile" in extra_files.ignored_config_keys
    assert "encryption.storagePath" in extra_files.ignored_config_keys
