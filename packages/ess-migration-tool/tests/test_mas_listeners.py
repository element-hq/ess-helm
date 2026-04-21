# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for MAS listeners filtering functionality."""

import logging

import yaml
from ess_migration_tool.mas import filter_mas_listeners
from ess_migration_tool.migration import ConfigValueTransformer


def test_filter_mas_listeners_with_no_listeners():
    """Test filtering when no listeners are provided."""
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), None)
    assert result is None


def test_filter_mas_listeners_with_ess_managed_only():
    """Test filtering when only ESS-managed listeners are provided."""
    listeners = [
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
    ]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is None


def test_filter_mas_listeners_with_custom_only():
    """Test filtering when only custom listeners are provided."""
    listeners = [
        {
            "name": "custom",
            "binds": [{"port": 9000, "host": "0.0.0.0"}],
            "resources": [{"name": "custom-resource"}, {"name": "another-custom"}],
        }
    ]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is not None
    assert "listeners.yml" in result
    assert "config" in result["listeners.yml"]
    # Verify the YAML structure contains our custom listener
    assert "port: 9000" in result["listeners.yml"]["config"]
    assert "custom-resource" in result["listeners.yml"]["config"]


def test_filter_mas_listeners_with_mixed():
    """Test filtering with mixed ESS-managed and custom listeners."""
    listeners = [
        {
            "name": "web",
            "binds": [{"port": 8080, "host": "0.0.0.0"}],
            "resources": [
                {"name": "human"},
                {"name": "custom-resource"},  # Mix of managed and custom
            ],
        },
        {"name": "custom", "binds": [{"port": 9000, "host": "0.0.0.0"}], "resources": [{"name": "custom-only"}]},
    ]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is not None
    assert "listeners.yml" in result
    # Should only contain the custom listener (port 9000)
    assert "port: 9000" in result["listeners.yml"]["config"]
    assert "custom-only" in result["listeners.yml"]["config"]
    # Should NOT contain the ESS-managed listener (port 8080)
    assert "port: 8080" not in result["listeners.yml"]["config"]


def test_filter_mas_listeners_with_empty_resources():
    """Test filtering when listener has no resources."""
    listeners = [{"name": "empty", "binds": [{"port": 8080, "host": "0.0.0.0"}], "resources": []}]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is None  # Empty resources should be filtered out


def test_filter_mas_listeners_with_no_binds():
    """Test filtering when listener has no binds."""
    listeners = [{"name": "no-binds", "binds": [], "resources": [{"name": "custom"}]}]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is None  # No binds means no port, should be filtered out


def test_filter_mas_listeners_with_multiple_binds():
    """Test filtering when listener has multiple binds, some managed and some custom."""
    listeners = [
        {
            "name": "multi-bind-managed",
            "binds": [
                {"port": 8080, "host": "0.0.0.0"},  # Managed port
                {"port": 9000, "host": "0.0.0.0"},  # Custom port
            ],
            "resources": [{"name": "custom-resource"}],
        },
        {
            "name": "multi-bind-custom",
            "binds": [
                {"port": 9001, "host": "0.0.0.0"},  # Custom port 1
                {"port": 9002, "host": "0.0.0.0"},  # Custom port 2
            ],
            "resources": [{"name": "custom-api"}],
        },
    ]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is not None
    assert "listeners.yml" in result

    # Parse the YAML to check content
    listeners_config = yaml.safe_load(result["listeners.yml"]["config"])
    listeners = listeners_config["http"]["listeners"]

    # Should only have the multi-bind-custom listener (multi-bind-managed should be filtered out)
    assert len(listeners) == 1
    assert listeners[0]["name"] == "multi-bind-custom"
    assert len(listeners[0]["binds"]) == 2  # Should preserve both custom binds
    assert listeners[0]["binds"][0]["port"] == 9001
    assert listeners[0]["binds"][1]["port"] == 9002


def test_filter_mas_listeners_with_different_bind_formats():
    """Test filtering with different bind formats (address, host/port, socket, fd)."""
    listeners = [
        {
            "name": "address-format-managed",
            "binds": [{"address": "[::]:8080"}],  # IPv6 managed port
            "resources": [{"name": "custom-api"}],
        },
        {
            "name": "address-format-custom",
            "binds": [{"address": "[::]:9000"}],  # IPv6 custom port
            "resources": [{"name": "custom-api"}],
        },
        {
            "name": "host-port-format-managed",
            "binds": [{"host": "localhost", "port": 8081}],  # Managed port
            "resources": [{"name": "custom-api"}],
        },
        {
            "name": "host-port-format-custom",
            "binds": [{"host": "localhost", "port": 9001}],  # Custom port
            "resources": [{"name": "custom-api"}],
        },
        {
            "name": "unix-socket",
            "binds": [{"socket": "/tmp/mas.sock"}],  # UNIX socket - incompatible with ESS
            "resources": [{"name": "custom-api"}],
        },
        {
            "name": "file-descriptor",
            "binds": [{"fd": 1, "kind": "tcp"}],  # File descriptor - incompatible with ESS
            "resources": [{"name": "custom-api"}],
        },
    ]
    result = filter_mas_listeners(ConfigValueTransformer(logging.getLogger(), {}), listeners)
    assert result is not None
    assert "listeners.yml" in result

    # Parse the YAML to check content
    listeners_config = yaml.safe_load(result["listeners.yml"]["config"])
    listeners = listeners_config["http"]["listeners"]

    # Should have custom listeners only (managed ones and incompatible ones filtered out)
    listener_names = [lstn["name"] for lstn in listeners]
    assert "address-format-managed" not in listener_names
    assert "address-format-custom" in listener_names
    assert "host-port-format-managed" not in listener_names
    assert "host-port-format-custom" in listener_names
    assert "unix-socket" not in listener_names  # UNIX sockets are incompatible with ESS
    assert "file-descriptor" not in listener_names  # File descriptors are incompatible with ESS

    # Only address and host/port formats should remain
    assert len(listeners) == 2
