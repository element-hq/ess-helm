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
            "args": {"database": "synapse", "user": "synapse", "host": "postgres", "port": 5432, "password": "test"}
        },
        "macaroon_secret_key": "test_macaroon_secret",
        "registration_shared_secret": "test_registration_secret",
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


@pytest.fixture
def synapse_config_with_signing_key(tmp_path, basic_synapse_config):
    """Synapse configuration with a signing key file."""
    # Create signing key file
    signing_key_file = tmp_path / "signing.key"
    signing_key_file.write_text("test_signing_key_content")

    # Add signing key to config
    config = basic_synapse_config.copy()
    config["signing_key_path"] = str(signing_key_file)

    return config


@pytest.fixture
def basic_mas_config(tmp_path):
    """Basic MAS configuration for testing."""
    return {
        "http": {"public_base": "https://auth.example.com", "bind": {"address": "0.0.0.0", "port": 8080}},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas?sslmode=prefer"},
        "secrets": {
            "encryption": "my_encryption_key",
        },
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
            "endpoint": "http://synapse:8008",
        },
    }


@pytest.fixture
def mas_config_with_keys(tmp_path, basic_mas_config):
    """MAS configuration with a signing key file."""
    # Create signing key file
    rsa_file = tmp_path / "rsa_key.pem"
    rsa_file.write_text("test_rsa_content")

    basic_mas_config["secrets"].setdefault("keys", [])
    basic_mas_config["secrets"]["keys"].append({"key_file": str(tmp_path / "rsa_key.pem"), "kid": "rsa"})
    basic_mas_config["secrets"]["keys"].append({"key": "prime256v1_key_value", "kid": "prime256v1"})
    basic_mas_config["secrets"]["keys"].append({"key": "key_value", "kid": "other"})
    return basic_mas_config


@pytest.fixture
def write_mas_config(tmp_path):
    """Helper fixture to write a MAS config file."""

    def _write_config(config_data):
        mas_config_file = tmp_path / "mas.yaml"
        with open(mas_config_file, "w") as f:
            yaml.dump(config_data, f)
        return mas_config_file

    return _write_config
