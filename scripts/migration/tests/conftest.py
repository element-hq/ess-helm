# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Pytest fixtures for migration tests.
Centralizes common test configurations to reduce duplication.
"""

import pytest
import yaml


@pytest.fixture
def basic_synapse_config():
    """Basic Synapse configuration for testing."""
    return {
        "server_name": "test.example.com",
        "public_baseurl": "https://matrix.example.com",
        "database": {
            "args": {
                "database": "synapse",
                "user": "synapse",
                "host": "postgres",
                "port": 5432,
            }
        },
    }


@pytest.fixture
def write_synapse_config(tmp_path):
    """Helper fixture to write a Synapse config file."""

    def _write_config(config_data):
        synapse_config_file = tmp_path / "synapse.yaml"
        with open(synapse_config_file, "w") as f:
            yaml.dump(config_data, f)
        return synapse_config_file

    return _write_config
