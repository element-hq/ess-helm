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
def synapse_config_with_instance_map(tmp_path, basic_synapse_config):
    """Synapse configuration with a signing key file."""
    # Add signing key to config
    config = basic_synapse_config.copy()
    config["instance_map"] = {
        "main": {"host": "main-instance.local", "port": 9093},
        "funny-name": {"host": "funny-instance.local", "port": 9093},
        "synchrotron": {"host": "synchro.local", "port": 9093},
        "synchrotron2": {"host": "synchro.local", "port": 9094},
    }

    return config


def synapse_config_with_email_templates(tmp_path, basic_synapse_config):
    """Synapse configuration with a signing key file."""
    # Create email templates directory
    templates_dir = tmp_path / "email_templates"
    templates_dir.mkdir()
    # Add password reset, registration templates
    (templates_dir / "password_reset.html").write_text("test_password_reset_content")
    (templates_dir / "registration.html").write_text("test_registration_content")

    # Add email templates to config
    config = basic_synapse_config.copy()
    config.setdefault("templates", {})["custom_template_directory"] = str(templates_dir)

    return config
