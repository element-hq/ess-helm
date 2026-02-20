# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Tests for YAML pipe formatting functionality.

Tests that multi-line strings in additional configurations are properly formatted
using the pipe (|) character for better readability in Helm charts.
"""

import yaml

from ..migration import ConfigValueTransformer
from ..outputs import generate_helm_values
from ..utils import yaml_dump_with_pipe_for_multiline


def test_multiline_string_uses_pipe():
    """Test that multi-line strings use pipe character."""
    config = {
        "log_config": """line1
line2
line3""",
        "simple_setting": "value",
    }

    result = yaml_dump_with_pipe_for_multiline(config)

    # Verify pipe character is present
    assert "|" in result, "Pipe character should be used for multi-line strings"

    # Verify it can be parsed back
    parsed = yaml.safe_load(result)
    assert parsed == config, "Round-trip parsing should work"


def test_single_line_strings_no_pipe():
    """Test that single-line strings don't use pipe character."""
    config = {"setting1": "value1", "setting2": "/path/to/file.yaml", "nested": {"key": "value"}}

    result = yaml_dump_with_pipe_for_multiline(config)

    # For single-line strings, the pipe should not be used
    # (unless it's part of the actual value, which it shouldn't be)
    lines = result.split("\n")
    for line in lines:
        if ":" in line and "|" in line:
            # This would indicate a pipe was used
            key_value = line.split(":", 1)
            if len(key_value) == 2:
                key = key_value[0].strip()
                if key in config and isinstance(config[key], str) and "\n" not in config[key]:
                    # This is a single-line string using pipe, which is wrong
                    raise AssertionError(f"Single-line string '{key}' should not use pipe character")


def test_nested_multiline_strings():
    """Test that nested multi-line strings use pipe character."""
    config = {
        "database": {
            "config": """host: localhost
port: 5432
ssl: true"""
        },
        "simple_setting": "value",
    }

    result = yaml_dump_with_pipe_for_multiline(config)

    # Verify pipe character is present
    assert "|" in result, "Pipe character should be used for nested multi-line strings"

    # Verify it can be parsed back
    parsed = yaml.safe_load(result)
    assert parsed == config, "Round-trip parsing should work for nested structures"


def test_complex_realistic_config():
    """Test with a complex, realistic configuration."""
    config = {
        "enable_metrics": True,
        "log_config": """# Log configuration
version: 1
formatters:
  simple:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
handlers:
  console:
    class: logging.StreamHandler
    formatter: simple
    stream: ext://sys.stdout""",
        "database": {"args": {"sslmode": "require"}},
        "email": {"smtp_host": "smtp.example.com", "smtp_port": 587},
    }

    result = yaml_dump_with_pipe_for_multiline(config)

    # Verify pipe character is used for the multi-line log_config
    assert "|" in result, "Pipe character should be used for multi-line log_config"

    # Verify all values are preserved
    parsed = yaml.safe_load(result)
    assert parsed == config, "All configuration values should be preserved"

    # Verify the log_config specifically
    assert parsed["log_config"] == config["log_config"], "Multi-line log_config should be preserved"


def test_empty_config():
    """Test with empty configuration."""
    config = {}

    result = yaml_dump_with_pipe_for_multiline(config)
    parsed = yaml.safe_load(result)

    assert parsed == config, "Empty config should round-trip correctly"


def test_config_with_lists():
    """Test that lists work correctly."""
    config = {"list_setting": ["item1", "item2", "item3"], "multiline_string": "line1\nline2"}

    result = yaml_dump_with_pipe_for_multiline(config)
    parsed = yaml.safe_load(result)

    assert parsed == config, "Configs with lists should work correctly"
    assert "|" in result, "Multi-line strings should still use pipe even with lists"


def test_additional_config_uses_pipe_for_multiline():
    """Test that additional config generation uses pipe for multi-line strings."""
    transformer = ConfigValueTransformer()

    source_config = {
        "log_config": """line1
line2
line3""",
        "simple_setting": "value1",
    }

    # Add additional config
    transformer.add_additional_config_to_component("synapse", source_config)

    # Get the generated YAML
    result = transformer.ess_config
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]

    # Verify pipe character is used
    assert "|" in yaml_content, "Additional config should use pipe for multi-line strings"

    # Verify it can be parsed back
    parsed = yaml.safe_load(yaml_content)
    assert parsed == source_config, "Additional config should round-trip correctly"


def test_additional_config_single_line_no_pipe():
    """Test that additional config with single-line strings doesn't force pipe usage."""
    transformer = ConfigValueTransformer()

    source_config = {"simple_setting": "value1", "path_setting": "/path/to/file.yaml"}

    # Add additional config
    transformer.add_additional_config_to_component("synapse", source_config)

    # Get the generated YAML
    result = transformer.ess_config
    yaml_content = result["synapse"]["additional"]["00-imported.yaml"]["config"]

    # Verify it can be parsed back (this is the main requirement)
    parsed = yaml.safe_load(yaml_content)
    assert parsed == source_config, "Single-line config should round-trip correctly"


def test_additional_config_mixed_content():
    """Test additional config with mixed single-line and multi-line content."""
    transformer = ConfigValueTransformer()

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

    # Add additional config
    transformer.add_additional_config_to_component("synapse", source_config)

    # Get the generated YAML
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


def test_helm_values_preserves_pipe_formatting():
    """Test that Helm values generation preserves pipe formatting in additional configs."""
    # Create ESS values with additional config that has pipe-formatted YAML
    ess_values = {
        "synapse": {
            "enabled": True,
            "postgres": {"host": "localhost", "database": "synapse"},
            "additional": {
                "00-imported.yaml": {
                    "config": """allowed_avatar_mimetypes:
- image/png
- image/jpeg
- image/gif
database:
  allow_unsafe_locale: false
  args:
    application_name: main-0
    cp_max: 10
    cp_min: 5
  name: psycopg2
enable_authenticated_media: true
enable_media_repo: true
enable_metrics: true
enable_registration: false
enable_set_avatar_url: true
enable_set_displayname: true
encryption_enabled_by_default_for_room_type: invite
"""
                }
            },
        }
    }

    # Generate Helm values
    helm_values_yaml = generate_helm_values(ess_values)

    # Verify that the additional config still contains pipe formatting
    assert "|" in helm_values_yaml, "Helm values should preserve pipe formatting"

    # Verify that the YAML is valid
    parsed = yaml.safe_load(helm_values_yaml)
    assert parsed == ess_values, "Helm values should round-trip correctly"

    # Verify that the additional config content is preserved in the generated YAML
    # The pipe character should be in the generated YAML string, not in the parsed data
    assert "|" in helm_values_yaml, "Pipe formatting should be preserved in generated Helm values"

    # Verify that the YAML is valid and content is preserved
    parsed = yaml.safe_load(helm_values_yaml)
    assert parsed == ess_values, "Helm values should round-trip correctly"

    # Verify that the additional config content is preserved
    additional_config_content = parsed["synapse"]["additional"]["00-imported.yaml"]["config"]
    assert "allowed_avatar_mimetypes" in additional_config_content
    assert "enable_metrics: true" in additional_config_content
