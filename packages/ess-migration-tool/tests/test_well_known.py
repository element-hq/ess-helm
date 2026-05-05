# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for well-known delegation migration."""

from ess_migration_tool.inputs import InputProcessor
from ess_migration_tool.models import GlobalOptions
from ess_migration_tool.well_known import (
    WellKnownMigration,
)


def test_strategy_names():
    """Test that strategies have correct names based on type parameter."""
    assert WellKnownMigration(GlobalOptions(), well_known_type="client").name == "Well Known Client"
    assert WellKnownMigration(GlobalOptions(), well_known_type="server").name == "Well Known Server"
    assert WellKnownMigration(GlobalOptions(), well_known_type="support").name == "Well Known Support"


def test_load_from_directory(tmp_path):
    """Test loading well-known files from a directory."""
    (tmp_path / "client.json").write_text('{"m.homeserver": {"base_url": "https://example.com"}}')
    (tmp_path / "server.json").write_text('{"m.server": "example.com:443"}')

    processor = InputProcessor()
    processor.load_well_known_inputs(dir_path=str(tmp_path))

    assert len(processor.inputs) == 2

    strategy_names = {i.name for i in processor.inputs}
    assert "Well Known Client" in strategy_names
    assert "Well Known Server" in strategy_names


def test_load_individual_files(tmp_path):
    """Test loading individual well-known files."""
    client_file = tmp_path / "client.json"
    client_file.write_text('{"m.homeserver": {"base_url": "https://test.com"}}')

    processor = InputProcessor()
    processor.load_well_known_inputs(client_path=str(client_file))

    assert len(processor.inputs) == 1
    assert processor.inputs[0].name == "Well Known Client"


def test_files_without_json_extension(tmp_path):
    """Test loading files without .json extension."""
    (tmp_path / "client").write_text('{"m.homeserver": {"base_url": "https://noport.com"}}')

    processor = InputProcessor()
    processor.load_well_known_inputs(dir_path=str(tmp_path))

    assert len(processor.inputs) == 1
    assert processor.inputs[0].name == "Well Known Client"


def test_cli_args_override_directory(tmp_path):
    """Test that CLI args override directory files."""
    dir_path = tmp_path / "well_known"
    dir_path.mkdir()
    (dir_path / "client.json").write_text('{"from": "directory"}')

    cli_client = tmp_path / "cli_client.json"
    cli_client.write_text('{"from": "cli"}')

    processor = InputProcessor()
    processor.load_well_known_inputs(dir_path=str(dir_path), client_path=str(cli_client))

    # Should only have CLI version
    assert len(processor.inputs) == 1
    assert processor.inputs[0].name == "Well Known Client"
    assert processor.inputs[0].config["from"] == "cli"
