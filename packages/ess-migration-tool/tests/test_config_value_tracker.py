# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""Tests for the ConfigValueTransformer class."""

import copy
import logging
from pathlib import Path

from ess_migration_tool.extra_files import ExtraFilesDiscovery
from ess_migration_tool.interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from ess_migration_tool.migration import TransformationSpec
from ess_migration_tool.models import DiscoveredPath, GlobalOptions, ValueSourceTracking


def test_config_value_tracker_basic(config_value_transformer):
    """Test basic ConfigValueTransformer functionality with dict-based transformations."""
    transformer = config_value_transformer(__name__)
    transformer.ess_config = {"unchanged": "value"}
    transformer.strategy_name = "TestStrategy"

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

    # Check tracked values via value_source_tracking
    tracked_source_paths = transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)
    assert "database.host" in tracked_source_paths
    assert "database.port" in tracked_source_paths
    assert "server_name" in tracked_source_paths
    assert len(tracked_source_paths) == 3

    # Check transformations
    transformations = transformer.results
    assert len(transformations) == 3

    # Check ESS config
    ess_config = transformer.ess_config
    assert ess_config["unchanged"] == "value"
    assert ess_config["postgres"]["host"] == "postgres"
    assert ess_config["postgres"]["port"] == 5432
    assert ess_config["serverName"] == "example.com"


def test_config_value_tracker_nested_dict(config_value_transformer):
    """Test ConfigValueTransformer with nested dictionaries."""
    transformer = config_value_transformer(__name__)
    transformer.strategy_name = "TestStrategy"

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

    # Check tracked values via value_source_tracking
    tracked_source_paths = transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)
    assert "database.connection.host" in tracked_source_paths
    assert "database.connection.port" in tracked_source_paths
    assert "database.credentials.user" in tracked_source_paths
    assert "server.name" in tracked_source_paths
    assert len(tracked_source_paths) == 4

    # Check ESS config
    ess_config = transformer.ess_config
    assert ess_config["database"]["connection"]["host"] == "postgres"
    assert ess_config["database"]["connection"]["port"] == 5432
    assert ess_config["database"]["credentials"]["user"] == "synapse"
    assert ess_config["server"]["name"] == "example.com"


def test_update_paths_in_config_basic(config_value_transformer):
    """Test update_paths_in_config with basic file path updates."""
    transformer = config_value_transformer(__name__)
    transformer.strategy_name = "TestStrategy"

    # Create a mock ExtraFilesDiscovery with discovered file paths
    class MockStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

        @property
        def component_root_key(self):
            return "some-component"

    class MockSecretStrategy(SecretDiscoveryStrategy):
        def __init__(self, global_options):
            self.global_options = global_options

        @property
        def ess_secret_schema(self):
            return {}

    # Create test source config with file paths
    source_config = {
        "templates": {
            "password_reset": "/path/to/password_reset.html",
            "registration": "/path/to/registration.html",
        },
        "other_setting": "preserved",
    }

    # Create discovered paths
    discovered_paths = [
        DiscoveredPath(
            config_key="templates.password_reset",
            source_file="test.yaml",
            source_path=Path("password_reset.html"),
            is_dir=False,
            skipped_reason=None,
        ),
        DiscoveredPath(
            config_key="templates.registration",
            source_file="test.yaml",
            source_path=Path("registration.html"),
            is_dir=False,
            skipped_reason=None,
        ),
    ]

    # Create ExtraFilesDiscovery instance
    extra_files_discovery = ExtraFilesDiscovery(
        strategy=MockStrategy(),
        pretty_logger=logging.Logger(__name__),
        secrets_strategy=MockSecretStrategy(global_options=GlobalOptions()),
        source_file="test.yaml",
        discovered_file_paths=discovered_paths,
    )

    # Test the update_paths_in_config method
    transformer.update_paths_in_config(source_config, extra_files_discovery)

    # Verify paths are updated correctly
    assert source_config["templates"]["password_reset"] == "/etc/some-component/extra/password_reset.html"
    assert source_config["templates"]["registration"] == "/etc/some-component/extra/registration.html"
    assert source_config["other_setting"] == "preserved"  # Non-file setting should be unchanged

    # Verify tracked values (only skipped paths are tracked)
    assert (
        len(transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)) == 0
    )  # No skipped paths in this test


def test_update_paths_in_config_with_skipped_paths(config_value_transformer):
    """Test update_paths_in_config with skipped file paths."""
    transformer = config_value_transformer(__name__)
    transformer.strategy_name = "TestStrategy"

    class MockStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

        @property
        def component_root_key(self):
            return "some-component"

    class MockSecretStrategy(SecretDiscoveryStrategy):
        def __init__(self, global_options):
            self.global_options = global_options

        @property
        def ess_secret_schema(self):
            return {}

    # Create test source config
    source_config = {
        "templates": {
            "password_reset": "/path/to/password_reset.html",
            "registration": "/path/to/registration.html",
        },
    }

    # Create discovered paths with one skipped
    discovered_paths = [
        DiscoveredPath(
            config_key="templates.password_reset",
            source_file="test.yaml",
            source_path=Path("password_reset.html"),
            is_dir=False,
            skipped_reason="File too large",
        ),
        DiscoveredPath(
            config_key="templates.registration",
            source_file="test.yaml",
            source_path=Path("registration.html"),
            is_dir=False,
            skipped_reason=None,
        ),
    ]

    extra_files_discovery = ExtraFilesDiscovery(
        strategy=MockStrategy(),
        pretty_logger=logging.Logger(__name__),
        secrets_strategy=MockSecretStrategy(global_options=GlobalOptions()),
        source_file="test.yaml",
        discovered_file_paths=discovered_paths,
    )

    # Test the update_paths_in_config method
    transformer.update_paths_in_config(source_config, extra_files_discovery)

    # Verify skipped path is not updated but is tracked
    assert source_config["templates"]["password_reset"] == "/path/to/password_reset.html"  # Unchanged
    assert source_config["templates"]["registration"] == "/etc/some-component/extra/registration.html"  # Updated

    assert "templates.password_reset" not in transformer.value_source_tracking.get_tracked_source_paths(
        transformer.strategy_name
    )
    assert "templates.registration" not in transformer.value_source_tracking.get_tracked_source_paths(
        transformer.strategy_name
    )
    assert len(transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)) == 0


def test_update_paths_in_config_empty_discovery(config_value_transformer):
    """Test update_paths_in_config with no discovered files."""
    transformer = config_value_transformer(__name__)
    transformer.strategy_name = "TestStrategy"

    class MockStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

        @property
        def component_root_key(self):
            return "some-component"

    class MockSecretStrategy(SecretDiscoveryStrategy):
        def __init__(self, global_options):
            self.global_options = global_options

        @property
        def ess_secret_schema(self):
            return {}

    # Create test source config
    source_config = {
        "templates": {
            "password_reset": "/path/to/password_reset.html",
        },
        "other_setting": "preserved",
    }

    # Create ExtraFilesDiscovery with no discovered paths
    extra_files_discovery = ExtraFilesDiscovery(
        strategy=MockStrategy(),
        pretty_logger=logging.Logger(__name__),
        secrets_strategy=MockSecretStrategy(global_options=GlobalOptions()),
        source_file="test.yaml",
        discovered_file_paths=[],
    )

    # Test the update_paths_in_config method
    updated_config = copy.deepcopy(source_config)
    transformer.update_paths_in_config(updated_config, extra_files_discovery)

    # Verify config is unchanged
    assert updated_config == source_config
    assert len(transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)) == 0


def test_update_paths_in_config_nested_config(config_value_transformer):
    """Test update_paths_in_config with nested configuration structures."""
    transformer = config_value_transformer(__name__)
    transformer.strategy_name = "TestStrategy"

    class MockStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

        @property
        def component_root_key(self):
            return "some-component"

    class MockSecretStrategy(SecretDiscoveryStrategy):
        def __init__(self, global_options):
            self.global_options = global_options

        @property
        def ess_secret_schema(self):
            return {}

    # Create test source config with nested structure
    source_config = {
        "email": {
            "smtp_host": "smtp.example.com",
            "template_dir": "/path/to/email/templates",
            "config": {
                "tls_cert": "/path/to/cert.pem",
                "tls_key": "/path/to/key.pem",
            },
        },
        "other_setting": "preserved",
    }

    # Create discovered paths
    discovered_paths = [
        DiscoveredPath(
            config_key="email.template_dir",
            source_file="test.yaml",
            source_path=Path("email/templates"),
            is_dir=True,
            skipped_reason=None,
        ),
        DiscoveredPath(
            config_key="email.config.tls_cert",
            source_file="test.yaml",
            source_path=Path("cert.pem"),
            is_dir=False,
            skipped_reason=None,
        ),
    ]

    extra_files_discovery = ExtraFilesDiscovery(
        strategy=MockStrategy(),
        pretty_logger=logging.Logger(__name__),
        secrets_strategy=MockSecretStrategy(global_options=GlobalOptions()),
        source_file="test.yaml",
        discovered_file_paths=discovered_paths,
    )

    # Test the update_paths_in_config method
    transformer.update_paths_in_config(source_config, extra_files_discovery)

    # Verify paths are updated correctly
    assert source_config["email"]["template_dir"] == "/etc/some-component/extra/templates"
    assert source_config["email"]["config"]["tls_cert"] == "/etc/some-component/extra/cert.pem"
    assert source_config["email"]["smtp_host"] == "smtp.example.com"  # Unchanged
    assert source_config["other_setting"] == "preserved"  # Unchanged

    # Verify tracked values (only skipped paths are tracked)
    assert (
        len(transformer.value_source_tracking.get_tracked_source_paths(transformer.strategy_name)) == 0
    )  # No skipped paths in this test


def test_get_conflicts_filters_none_values():
    """Test that get_conflicts() filters out sources with None values."""
    tracking = ValueSourceTracking()

    # Add sources where one has a real value and another has None
    tracking.add_source("serverName", "Synapse", "synapse.example.com", "server_name")
    tracking.add_source("serverName", "MAS", None, "matrix.homeserver")

    # No conflict should be reported because MAS's None is filtered out
    conflicts = tracking.get_conflicts()
    assert conflicts == {}


def test_get_conflicts_preserves_real_conflicts():
    """Test that get_conflicts() still reports conflicts between non-None values."""
    tracking = ValueSourceTracking()

    # Add sources where both have real but different values
    tracking.add_source("serverName", "Synapse", "synapse.example.com", "server_name")
    tracking.add_source("serverName", "MAS", "mas.example.com", "matrix.homeserver")

    # Conflict should be reported
    conflicts = tracking.get_conflicts()
    assert "serverName" in conflicts
    assert len(conflicts["serverName"]) == 2
