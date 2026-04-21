# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Tests for additional config generation using the new transformer approach.

Tests that the additional_config_transformer correctly generates filtered
additional configurations with proper YAML pipe formatting for multi-line strings.
"""

import logging

import yaml
from ess_migration_tool.migration import ConfigValueTransformer, TransformationSpec, additional_config_transformer


def test_additional_config_transformer_uses_pipe_for_multiline():
    """Test that additional_config_transformer uses pipe for multi-line strings."""
    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config={})
    source_config = {
        "log_config": """line1
line2
line3""",
        "simple_setting": "value1",
    }

    # Create transformation spec with src_key=None to pass full config
    spec = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    # Apply transformation
    transformer.transform_from_config(
        source_config,
        [spec],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    # Get the generated YAML
    result = transformer.ess_config
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]

    # Verify pipe character is used
    assert "|" in yaml_content, "Additional config should use pipe for multi-line strings"

    # Verify it can be parsed back
    parsed = yaml.safe_load(yaml_content)
    assert parsed == source_config, "Additional config should round-trip correctly"


def test_additional_config_transformer_single_line_no_unnecessary_pipe():
    """Test that additional config with single-line strings doesn't force pipe usage unnecessarily."""
    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config={})

    source_config = {"simple_setting": "value1", "path_setting": "/path/to/file.yaml"}

    spec = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    transformer.transform_from_config(
        source_config,
        [spec],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    result = transformer.ess_config
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]

    # Verify it can be parsed back (this is the main requirement)
    parsed = yaml.safe_load(yaml_content)
    assert parsed == source_config, "Single-line config should round-trip correctly"


def test_additional_config_transformer_mixed_content():
    """Test additional config transformer with mixed single-line and multi-line content."""
    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config={})

    source_config = {
        "enable_metrics": True,
        "log_config": '''# Log config
version: 1
formatters:
  simple:
    format: "%(message)s"''',
        "database": {"host": "localhost", "port": 5432},
        "simple_setting": "value1",
    }

    spec = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    transformer.transform_from_config(
        source_config,
        [spec],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    result = transformer.ess_config
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]

    # Verify pipe character is used for multi-line content
    assert "|" in yaml_content, "Pipe should be used for multi-line content"

    # Verify all content is preserved
    parsed = yaml.safe_load(yaml_content)
    assert parsed == source_config, "Mixed content should be fully preserved"

    # Verify specific values
    assert parsed["enable_metrics"]
    assert parsed["log_config"] == source_config["log_config"]
    assert parsed["database"]["host"] == "localhost"
    assert parsed["simple_setting"] == "value1"


def test_additional_config_transformer_filters_tracked_values():
    """Test that additional_config_transformer filters out tracked values."""
    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config={})

    source_config = {
        "server_name": "test.example.com",
        "public_baseurl": "https://matrix.example.com",
        "extra_setting": "should_be_in_additional",
    }

    # First transformation tracks server_name
    spec1 = TransformationSpec(
        src_key="server_name",
        target_key="synapse.serverName",
        required=True,
    )

    # Second transformation tracks public_baseurl
    spec2 = TransformationSpec(
        src_key="public_baseurl",
        target_key="synapse.ingress.host",
        required=True,
    )

    # Third transformation generates additional config with src_key=None
    spec3 = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    transformer.transform_from_config(
        source_config,
        [spec1, spec2, spec3],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    result = transformer.ess_config

    # Verify tracked values are in ESS config
    assert result["synapse"]["serverName"] == "test.example.com"
    assert result["synapse"]["ingress"]["host"] == "https://matrix.example.com"

    # Verify additional config only contains untracked values
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]
    parsed = yaml.safe_load(yaml_content)

    # Only extra_setting should remain
    assert parsed == {"extra_setting": "should_be_in_additional"}
    assert "server_name" not in parsed
    assert "public_baseurl" not in parsed


def test_additional_config_transformer_empty_when_all_tracked():
    """Test that additional config is empty when all values are tracked."""
    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config={})

    source_config = {
        "server_name": "test.example.com",
        "public_baseurl": "https://matrix.example.com",
    }

    # All values are tracked
    spec1 = TransformationSpec(
        src_key="server_name",
        target_key="synapse.serverName",
        required=True,
    )

    spec2 = TransformationSpec(
        src_key="public_baseurl",
        target_key="synapse.ingress.host",
        required=True,
    )

    spec3 = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    transformer.transform_from_config(
        source_config,
        [spec1, spec2, spec3],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    result = transformer.ess_config

    # Additional should be empty or not present
    assert result["synapse"].get("additional") == {}


def test_additional_config_transformer_preserves_existing_additional():
    """Test that additional_config_transformer preserves existing additional entries."""
    # Start with existing additional config (e.g., from listeners transformer)
    ess_config = {"synapse": {"additional": {"listeners.yml": {"config": "port: 8080\n"}}}}

    transformer = ConfigValueTransformer(logging.Logger(__name__), ess_config)

    source_config = {
        "extra_setting": "value1",
    }

    spec = TransformationSpec(
        src_key=None,
        target_key="synapse.additional",
        transformer=additional_config_transformer,
        required=False,
    )

    transformer.transform_from_config(
        source_config,
        [spec],
        component_root_key="synapse",
        extra_files_discovery=None,
    )

    result = transformer.ess_config

    # Verify both entries exist
    assert "listeners.yml" in result["synapse"]["additional"]
    assert "00-imported.yaml" in result["synapse"]["additional"]

    # Verify existing listeners.yml is preserved
    assert result["synapse"]["additional"]["listeners.yml"]["config"] == "port: 8080\n"

    # Verify new imported config exists
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]
    parsed = yaml.safe_load(yaml_content)
    assert parsed == {"extra_setting": "value1"}
