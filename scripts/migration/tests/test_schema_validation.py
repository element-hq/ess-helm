# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Tests for validating MigrationEngine output against the Helm chart schema
and testing the new credential schema functionality.
"""

import json
import logging
from pathlib import Path

import jsonschema
import pytest

from ..engine import MigrationEngine
from ..inputs import InputProcessor

# Path to the Helm chart schema
SCHEMA_PATH = Path("charts/matrix-stack/values.schema.json")


def load_helm_schema():
    """Load the Helm chart schema from file."""
    if not SCHEMA_PATH.exists():
        pytest.skip(f"Schema file not found: {SCHEMA_PATH}")

    with open(SCHEMA_PATH) as f:
        return json.load(f)


def validate_against_schema(data: dict, schema: dict):
    """Validate data against the Helm chart schema."""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e)


def test_migration_output_schema_validation(tmp_path, basic_synapse_config, write_synapse_config):
    """Test that MigrationEngine output validates against the Helm chart schema."""

    # Load the Helm chart schema
    schema = load_helm_schema()

    synapse_path = write_synapse_config(basic_synapse_config)

    # Load migration input
    input_processor = InputProcessor()
    input_processor.load_migration_input(
        name="synapse",
        config_path=synapse_path,
    )

    # Create and run migration engine
    engine = MigrationEngine(input_processor=input_processor)
    ess_values = engine.run_migration()

    # Validate the output against the schema
    is_valid, error = validate_against_schema(ess_values, schema)

    if not is_valid:
        logging.error(f"Schema validation failed: {error}")
        logging.error(f"Generated ESS values: {json.dumps(ess_values, indent=2)}")
        pytest.fail(f"Migration output failed schema validation: {error}")

    # Additional assertions to ensure the migration produced expected structure
    assert "serverName" in ess_values
    assert ess_values["serverName"] == "test.example.com"
    assert "synapse" in ess_values
    assert ess_values["synapse"]["enabled"] is True
