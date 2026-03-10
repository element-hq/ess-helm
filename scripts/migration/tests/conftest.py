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


@pytest.fixture
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


@pytest.fixture
def synapse_config_with_ca_federation_list(tmp_path, basic_synapse_config):
    """Synapse configuration with a signing key file."""
    # Create email templates directory
    templates_dir = tmp_path / "ca"
    templates_dir.mkdir()
    # Add password reset, registration templates
    (templates_dir / "ca1.pem").write_text("CA1")
    (templates_dir / "ca-second.pem").write_text("CA2")
    (templates_dir / "another-ca.pem").write_text("CA3")

    # Add email templates to config
    config = basic_synapse_config.copy()
    config["federation_custom_ca_list"] = [
        str(templates_dir / "ca1.pem"),
        str(templates_dir / "ca-second.pem"),
        str(templates_dir / "another-ca.pem"),
    ]

    return config


@pytest.fixture
def basic_mas_config():
    """Basic MAS configuration for testing."""
    return {
        "http": {"public_base": "https://auth.example.com", "bind": {"address": "0.0.0.0", "port": 8080}},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas?sslmode=prefer"},
        "secrets": {"encryption": "my_encryption_key"},
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
            "endpoint": "http://synapse:8008",
        },
    }


@pytest.fixture
def basic_mas_config_with_keys(tmp_path, basic_mas_config):
    """MAS configuration with keys directory and sample keys."""

    # Create keys directory
    keys_dir = tmp_path / "mas" / "keys"
    keys_dir.mkdir(parents=True)

    # Generate and save RSA key using PKCS1 format
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    rsa_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (keys_dir / "rsa_key.pem").write_bytes(rsa_pem)

    # Generate and save ECDSA key using PKCS1 format
    ecdsa_key = ec.generate_private_key(ec.SECP256R1(), backend=default_backend())
    ecdsa_pem = ecdsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (keys_dir / "ecdsa_key.pem").write_bytes(ecdsa_pem)

    # Update config with keys directory
    mas_config = basic_mas_config.copy()
    mas_config["secrets"]["keys_dir"] = str(keys_dir)

    return mas_config


@pytest.fixture
def write_mas_config(tmp_path):
    """Helper fixture to write a MAS config file."""

    def _write_config(config_data):
        mas_config_file = tmp_path / "mas.yaml"
        with open(mas_config_file, "w") as f:
            yaml.dump(config_data, f)
        return mas_config_file

    return _write_config


@pytest.fixture
def rsa_key_pem():
    """Generate a sample RSA private key in PEM format using PKCS1."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def rsa_key_der():
    """Generate a sample RSA private key in DER format using PKCS1."""

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def ecdsa_key_pem():
    """Generate a sample ECDSA Prime256v1 private key in PEM format using PKCS1."""

    key = ec.generate_private_key(ec.SECP256R1(), backend=default_backend())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def ecdsa_key_der():
    """Generate a sample ECDSA Prime256v1 private key in DER format using PKCS1."""

    key = ec.generate_private_key(ec.SECP256R1(), backend=default_backend())
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
