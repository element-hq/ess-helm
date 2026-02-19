# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""Tests for the ConfigValueTransformer class."""

from ..migration import ConfigValueTransformer, TransformationSpec


def test_config_value_tracker_basic():
    """Test basic ConfigValueTransformer functionality with dict-based transformations."""
    transformer = ConfigValueTransformer(ess_config={"unchanged": "value"})

    # Create a test config
    config = {
        "database": {
            "host": "postgres",
            "port": 5432,
        },
        "server_name": "example.com",
    }

    # Transform some values using TransformationSpec
    transformer.transform_from_config(
        config,
        [
            TransformationSpec(src_key="database.host", target_key="postgres.host"),
            TransformationSpec(src_key="database.port", target_key="postgres.port"),
            TransformationSpec(src_key="server_name", target_key="serverName"),
        ],
    )

    # Check tracked values
    tracked_values = transformer.tracked_values
    assert "database.host" in tracked_values
    assert "database.port" in tracked_values
    assert "server_name" in tracked_values
    assert len(tracked_values) == 3

    # Check transformations
    transformations = transformer.results
    assert len(transformations) == 3

    # Check ESS config
    ess_config = transformer.ess_config
    assert ess_config["unchanged"] == "value"
    assert ess_config["postgres"]["host"] == "postgres"
    assert ess_config["postgres"]["port"] == 5432
    assert ess_config["serverName"] == "example.com"


def test_config_value_tracker_filter_config():
    """Test ConfigValueTransformer filter_config functionality."""
    transformer = ConfigValueTransformer()

    # Create a test config
    config = {
        "database": {
            "host": "postgres",
            "port": 5432,
        },
        "server_name": "example.com",
    }

    # Transform some values
    transformer.transform_from_config(
        config,
        [
            TransformationSpec(src_key="database.host", target_key="postgres.host"),
            TransformationSpec(src_key="database.port", target_key="postgres.port"),
            TransformationSpec(src_key="server_name", target_key="serverName"),
        ],
    )

    # Create a config to filter
    config = {
        "database": {
            "host": "postgres",
            "port": 5432,
            "name": "synapse",  # Not tracked
        },
        "server_name": "example.com",
        "other_setting": "preserved",
    }

    # Filter the config
    filtered_config = transformer.filter_config(config)

    # Check that tracked values are removed
    assert "database" in filtered_config
    assert "host" not in filtered_config["database"]
    assert "port" not in filtered_config["database"]
    assert "name" in filtered_config["database"]  # Not tracked, should be preserved
    assert "server_name" not in filtered_config
    assert "other_setting" in filtered_config  # Not tracked, should be preserved


def test_config_value_tracker_nested_dict():
    """Test ConfigValueTransformer with nested dictionaries."""
    transformer = ConfigValueTransformer()

    # Create a nested config
    config = {
        "database": {
            "connection": {
                "host": "postgres",
                "port": 5432,
            },
            "credentials": {
                "user": "synapse",
                "password": "secret",
            },
        },
        "server": {
            "name": "example.com",
        },
    }

    # Transform values from the nested dict using explicit TransformationSpecs
    transformer.transform_from_config(
        config,
        [
            TransformationSpec(src_key="database.connection.host", target_key="database.connection.host"),
            TransformationSpec(src_key="database.connection.port", target_key="database.connection.port"),
            TransformationSpec(src_key="database.credentials.user", target_key="database.credentials.user"),
            TransformationSpec(src_key="server.name", target_key="server.name"),
        ],
    )

    # Check tracked values
    tracked_values = transformer.tracked_values
    assert "database.connection.host" in tracked_values
    assert "database.connection.port" in tracked_values
    assert "database.credentials.user" in tracked_values
    assert "server.name" in tracked_values
    assert len(tracked_values) == 4

    # Check ESS config
    ess_config = transformer.ess_config
    assert ess_config["database"]["connection"]["host"] == "postgres"
    assert ess_config["database"]["connection"]["port"] == 5432
    assert ess_config["database"]["credentials"]["user"] == "synapse"
    assert ess_config["server"]["name"] == "example.com"


def test_config_value_tracker_empty():
    """Test ConfigValueTransformer with no tracked values."""
    transformer = ConfigValueTransformer()

    # Create a config to filter
    config = {
        "database": {
            "host": "postgres",
            "port": 5432,
        },
        "server_name": "example.com",
    }

    # Filter the config (no values tracked)
    filtered_config = transformer.filter_config(config)

    # Should be unchanged
    assert filtered_config == config

    # ESS config should be empty
    assert transformer.ess_config == {}
