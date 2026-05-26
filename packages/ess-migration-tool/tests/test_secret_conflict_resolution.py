# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for secret conflict resolution functionality.
Tests the DiscoveredSecretTracking class and integration with SecretDiscovery.
"""

import logging

from ess_migration_tool.models import DiscoveredSecretTracking, GlobalOptions
from ess_migration_tool.secrets import SecretDiscovery
from ess_migration_tool.synapse import SynapseSecretDiscovery


def test_add_source_and_is_discovered():
    """Test adding a source and checking if secret is discovered."""
    tracking = DiscoveredSecretTracking()

    assert not tracking.is_discovered("synapse.signingKey")

    tracking.add_source("synapse.signingKey", "synapse", "test_key_value", "signing_key")

    assert tracking.is_discovered("synapse.signingKey")


def test_get_all_values():
    """Test that get_all_values returns all discovered values."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "value1", "path1")
    tracking.add_source("synapse.signingKey", "synapse", "value2", "path2")

    values = tracking.get_all_values("synapse.signingKey")
    assert len(values) == 2
    assert "value1" in values
    assert "value2" in values


def test_get_all_values_empty():
    """Test get_all_values for undiscovered secret."""
    tracking = DiscoveredSecretTracking()

    values = tracking.get_all_values("synapse.signingKey")
    assert values == []


def test_no_conflict_with_same_value():
    """Test that no conflict is detected when all sources have the same value."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "same_value", "path1")
    tracking.add_source("synapse.signingKey", "mas", "same_value", "path2")

    conflicts = tracking.get_conflicts()
    assert "synapse.signingKey" not in conflicts


def test_conflict_with_different_values():
    """Test that conflict is detected when sources have different values from different strategies."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "value1", "path1")
    tracking.add_source("synapse.signingKey", "mas", "value2", "path2")

    conflicts = tracking.get_conflicts()
    assert "synapse.signingKey" in conflicts
    assert len(conflicts["synapse.signingKey"]) == 2


def test_no_conflict_with_single_source():
    """Test that no conflict is detected with a single source."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "value1", "path1")

    conflicts = tracking.get_conflicts()
    assert "synapse.signingKey" not in conflicts


def test_no_conflict_same_strategy_different_values():
    """Test that same strategy with different values doesn't count as conflict."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "value1", "path1")
    tracking.add_source("synapse.signingKey", "synapse", "value2", "path2")

    conflicts = tracking.get_conflicts()
    assert "synapse.signingKey" not in conflicts


def test_get_strategies_for_secret():
    """Test getting all strategies that discovered a secret."""
    tracking = DiscoveredSecretTracking()

    tracking.add_source("synapse.signingKey", "synapse", "value1", "path1")
    tracking.add_source("synapse.signingKey", "mas", "value2", "path2")

    strategies = tracking.get_strategies_for_secret("synapse.signingKey")
    assert len(strategies) == 2
    assert "synapse" in strategies
    assert "mas" in strategies


def test_get_strategies_for_undiscovered_secret():
    """Test getting strategies for an undiscovered secret."""
    tracking = DiscoveredSecretTracking()

    strategies = tracking.get_strategies_for_secret("synapse.signingKey")
    assert strategies == []


def test_secret_discovery_uses_tracking():
    """Test that SecretDiscovery uses tracking when provided."""
    tracking = DiscoveredSecretTracking()
    global_options = GlobalOptions()
    strategy = SynapseSecretDiscovery(global_options)

    discovery = SecretDiscovery(
        strategy=strategy,
        source_file="test.yaml",
        summary_logger=logging.getLogger("test"),
        global_options=global_options,
        secret_tracking=tracking,
    )

    assert discovery.secret_tracking is tracking


def test_discovered_secret_registered_with_tracking():
    """Test that discovered secrets are registered with tracking."""
    tracking = DiscoveredSecretTracking()
    global_options = GlobalOptions()
    strategy = SynapseSecretDiscovery(global_options)

    discovery = SecretDiscovery(
        strategy=strategy,
        source_file="test.yaml",
        summary_logger=logging.getLogger("test"),
        global_options=global_options,
        secret_tracking=tracking,
    )

    test_config = {"signing_key": "test_signing_key_value"}

    discovery.discover_secrets(test_config)

    assert tracking.is_discovered("synapse.signingKey")


def test_synapse_signing_key_not_optional():
    """Test that synapse.signingKey is not optional in SynapseSecretDiscovery."""
    global_options = GlobalOptions()
    strategy = SynapseSecretDiscovery(global_options)

    schema = strategy.ess_secret_schema
    signing_key_config = schema.get("synapse.signingKey")

    assert signing_key_config is not None
    assert not signing_key_config.optional
