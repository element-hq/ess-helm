# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import yaml
from ess_migration_tool.synapse import filter_listeners


def test_filter_listeners_with_chart_managed_resources(config_value_transformer):
    """Test that filter_listeners removes listeners with only chart-managed resources."""
    listeners = [
        {
            "port": 8008,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["client", "federation"], "compress": False}],
        },
        {
            "port": 9093,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["replication"], "compress": False}],
        },
        {
            "port": 9001,
            "type": "metrics",
            "resources": [{"names": ["metrics"], "compress": False}],
        },
        {
            "port": 8080,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["health"], "compress": False}],
        },
    ]

    result = filter_listeners(config_value_transformer(__name__), listeners)

    # Should return None since all listeners serve only chart-managed resources
    assert result is None


def test_filter_listeners_with_custom_resources(config_value_transformer):
    """Test that filter_listeners keeps listeners with custom resources."""
    listeners = [
        {
            "port": 8008,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["client", "federation"], "compress": False}],
        },
        {
            "port": 1200,
            "tls": True,
            "type": "http",
            "resources": [{"names": ["custom_api"], "compress": False}],
        },
        {
            "port": 9093,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["replication"], "compress": False}],
        },
        {
            "port": 8080,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["health"], "compress": False}],
        },
    ]

    result = filter_listeners(config_value_transformer(__name__), listeners)

    # Should keep only the listener with custom resource
    assert result is not None
    assert isinstance(result, dict)
    assert "listeners.yml" in result
    assert "config" in result["listeners.yml"]
    # Parse the YAML config to verify content
    parsed_result = yaml.safe_load(result["listeners.yml"]["config"])
    assert parsed_result == {
        "listeners": [
            {
                "port": 1200,
                "tls": True,
                "type": "http",
                "resources": [{"names": ["custom_api"], "compress": False}],
            }
        ]
    }


def test_filter_listeners_with_no_listeners(config_value_transformer):
    """Test that filter_listeners handles None input."""
    result = filter_listeners(config_value_transformer(__name__), None)
    assert result is None


def test_filter_listeners_with_empty_list(config_value_transformer):
    """Test that filter_listeners handles empty list."""
    result = filter_listeners(config_value_transformer(__name__), [])
    assert result is None


def test_filter_listeners_with_mixed_resources(config_value_transformer):
    """Test that filter_listeners correctly filters mixed chart-managed and custom resources."""
    listeners = [
        {
            "port": 8008,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["client", "federation"], "compress": False}],
        },
        {
            "port": 8448,
            "tls": True,
            "type": "http",
            "resources": [{"names": ["dropped_as_conflicting_port"], "compress": False}],
        },
        {
            "port": 9093,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["replication"], "compress": False}],
        },
        {
            "port": 8449,
            "tls": True,
            "type": "http",
            "resources": [{"names": ["another_custom"], "compress": False}],
        },
        {
            "port": 9001,
            "type": "metrics",
            "resources": [{"names": ["metrics"], "compress": False}],
        },
        {
            "port": 8080,
            "tls": False,
            "type": "http",
            "resources": [{"names": ["health"], "compress": False}],
        },
        {
            "port": 8450,
            "tls": True,
            "type": "http",
            "resources": [{"names": ["third_custom"], "compress": False}],
        },
    ]

    result = filter_listeners(config_value_transformer(__name__), listeners)

    # Should keep only the listeners with custom resources and no ESS-managed port
    assert result is not None
    assert isinstance(result, dict)
    assert "listeners.yml" in result
    assert "config" in result["listeners.yml"]
    # Parse the YAML config to verify content
    parsed_result = yaml.safe_load(result["listeners.yml"]["config"])
    assert parsed_result == {
        "listeners": [
            {
                "port": 8449,
                "tls": True,
                "type": "http",
                "resources": [{"names": ["another_custom"], "compress": False}],
            },
            {
                "port": 8450,
                "tls": True,
                "type": "http",
                "resources": [{"names": ["third_custom"], "compress": False}],
            },
        ]
    }


def test_filter_listeners_with_string_resource_names(config_value_transformer):
    """Test that filter_listeners handles string resource names (not just lists)."""
    listeners = [
        {
            "port": 8008,
            "tls": False,
            "type": "http",
            "resources": [{"names": "client", "compress": False}],  # String instead of list
        },
        {
            "port": 1200,
            "tls": True,
            "type": "http",
            "resources": [{"names": "custom_api", "compress": False}],  # String instead of list
        },
    ]

    result = filter_listeners(config_value_transformer(__name__), listeners)

    # Should keep only the listener with custom resource
    assert result is not None
    assert isinstance(result, dict)
    assert "listeners.yml" in result
    assert "config" in result["listeners.yml"]
    # Parse the YAML config to verify content
    parsed_result = yaml.safe_load(result["listeners.yml"]["config"])
    assert parsed_result == {
        "listeners": [
            {
                "port": 1200,
                "tls": True,
                "type": "http",
                "resources": [{"names": ["custom_api"], "compress": False}],
            }
        ]
    }
