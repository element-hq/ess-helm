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

import jsonschema  # type: ignore[import-untyped]
import pytest
from ess_migration_tool.element_web import ElementWebMigration
from ess_migration_tool.engine import MigrationEngine
from ess_migration_tool.hookshot import HookshotMigration
from ess_migration_tool.inputs import InputProcessor
from ess_migration_tool.mas import MASMigration
from ess_migration_tool.models import GlobalOptions
from ess_migration_tool.synapse import SynapseMigration
from ess_migration_tool.well_known import WellKnownMigration

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


def is_valid_schema_path(schema: dict, target_key: str | None) -> bool:
    """
    Check if a target_key path exists in the schema.

    Returns True if:
    - target_key is None or empty (full config replacement via transformers)
    - The path exists in the schema's properties

    Handles nested paths like 'synapse.replicas' by traversing the schema.
    Handles wildcard paths (e.g., 'image.pullSecrets.*.name') via items.properties.
    Does NOT validate:
    - oneOf/anyOf conditions
    - The 'additional' field (allows arbitrary config)
    """
    if not target_key:
        return True

    # Skip validation for 'additional' paths as they contain arbitrary config
    if "additional" in target_key:
        return True

    parts = target_key.split(".")
    current = schema
    i = 0

    while i < len(parts):
        part = parts[i]

        # Look ahead: if next part is a wildcard, handle array access
        if i + 1 < len(parts) and parts[i + 1] == "*":
            # Current part should be an array in current's properties
            if "properties" not in current:
                return False
            if part not in current["properties"]:
                return False
            array_schema = current["properties"][part]
            if not isinstance(array_schema, dict):
                return False
            # Check if it's an array with items
            if array_schema.get("type") != "array" or "items" not in array_schema:
                return False
            # Skip to the part after the wildcard
            if i + 2 >= len(parts):
                return False
            next_part = parts[i + 2]  # Part after the wildcard
            items = array_schema["items"]
            if "properties" not in items:
                return False
            if next_part not in items["properties"]:
                return False
            # Continue with items schema, skipping the wildcard and array index
            current = items
            i += 2  # Skip the wildcard
            continue

        # Handle wildcard patterns - shouldn't happen if look-ahead works
        if part == "*":
            return False

        if "properties" not in current:
            return False
        if part not in current["properties"]:
            return False
        current = current["properties"][part]
        if not isinstance(current, dict):
            return False

        i += 1

    return True


def test_transformation_specs_target_keys_valid():
    """
    Test that all TransformationSpec target_keys reference valid paths in the Helm chart schema.

    This catches issues where we're migrating to non-existent paths in the ESS Helm chart.
    Tests Synapse, MAS, Element Web, Hookshot, and Well Known strategies.
    """
    schema = load_helm_schema()
    global_opts = GlobalOptions()

    # Strategies to test - Synapse, MAS, Element Web, Hookshot, Well Known
    strategies = [
        SynapseMigration(global_opts),
        MASMigration(global_opts),
        ElementWebMigration(global_opts),
        HookshotMigration(global_opts),
        WellKnownMigration(global_opts, well_known_type="client"),
        WellKnownMigration(global_opts, well_known_type="server"),
        WellKnownMigration(global_opts, well_known_type="support"),
    ]

    invalid_targets = []
    for strategy in strategies:
        for spec in strategy.transformations:
            if spec.target_key and not is_valid_schema_path(schema, spec.target_key):
                invalid_targets.append(f"{strategy.name}: {spec.target_key}")

    if invalid_targets:
        pytest.fail("TransformationSpec target_keys not in schema:\n" + "\n".join(invalid_targets))


def test_migration_output_schema_validation(tmp_path, synapse_config_with_signing_key, write_synapse_config):
    """Test that MigrationEngine output validates against the Helm chart schema."""

    # Load the Helm chart schema
    schema = load_helm_schema()

    synapse_path = write_synapse_config(synapse_config_with_signing_key)

    # Load migration input
    input_processor = InputProcessor()
    input_processor.load_migration_input(
        name="Synapse",
        config_path=synapse_path,
    )

    # Create and run migration engine
    engine = MigrationEngine(input_processor=input_processor, pretty_logger=logging.getLogger())

    # Set database mode directly to avoid prompting (simulate --database-mode existing)
    engine.global_options.use_existing_database = True

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
