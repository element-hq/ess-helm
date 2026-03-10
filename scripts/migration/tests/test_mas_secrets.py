# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from scripts.migration.secrets import SecretDiscovery

from ..mas import MASSecretDiscovery


def test_discover_secrets_from_mas_config(basic_mas_config):
    """Test MAS config with PostgreSQL database URI using transformer."""
    mas_config = basic_mas_config.copy()
    # The basic_mas_config already has database.uri with password

    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Should have discovered the password from database URI using transformer
    assert "matrixAuthenticationService.postgres.password" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.postgres.password"].value == "mas_password"
    assert "matrixAuthenticationService.encryptionSecret" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.encryptionSecret"].value == "my_encryption_key"


def test_key_detection_utility(
    rsa_key_pem,
    rsa_key_der,
    ecdsa_key_pem,
    ecdsa_key_der,
    ecdsa_secp256k1_key_pem,
    ecdsa_secp256k1_key_der,
    ecdsa_secp384r1_key_pem,
    ecdsa_secp384r1_key_der,
):
    """Test the key type detection utility function."""
    from ..utils import detect_key_type

    # Test RSA PEM
    assert detect_key_type(rsa_key_pem) == "rsa"

    # Test ECDSA Prime256v1 PEM
    assert detect_key_type(ecdsa_key_pem) == "ecdsaPrime256v1"

    # Test RSA DER
    assert detect_key_type(rsa_key_der) == "rsa"

    # Test ECDSA Prime256v1 DER
    assert detect_key_type(ecdsa_key_der) == "ecdsaPrime256v1"

    # Test ECDSA Secp256k1 PEM
    assert detect_key_type(ecdsa_secp256k1_key_pem) == "ecdsaSecp256k1"

    # Test ECDSA Secp256k1 DER
    assert detect_key_type(ecdsa_secp256k1_key_der) == "ecdsaSecp256k1"

    # Test ECDSA Secp384r1 PEM
    assert detect_key_type(ecdsa_secp384r1_key_pem) == "ecdsaSecp384r1"

    # Test ECDSA Secp384r1 DER
    assert detect_key_type(ecdsa_secp384r1_key_der) == "ecdsaSecp384r1"

    # Test invalid content
    assert detect_key_type(b"invalid content") == "unknown"
    assert detect_key_type(b"") == "unknown"


def test_keys_dir_discovery(tmp_path, rsa_key_pem, ecdsa_key_pem):
    """Test key discovery from keys_dir configuration."""
    # Create keys directory
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    # Write RSA key
    rsa_key_file = keys_dir / "rsa_key.pem"
    rsa_key_file.write_bytes(rsa_key_pem)

    # Write ECDSA key
    ecdsa_key_file = keys_dir / "ecdsa_key.pem"
    ecdsa_key_file.write_bytes(ecdsa_key_pem)

    # Create MAS config with keys_dir
    mas_config = {
        "http": {"public_base": "https://auth.example.com"},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas"},
        "secrets": {"encryption": "my_encryption_key", "keys_dir": str(keys_dir)},
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
        },
    }

    # Test discovery
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Verify RSA key was discovered
    assert "matrixAuthenticationService.keys.rsa" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].value == rsa_key_pem.decode("utf-8")
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].config_key == "secrets.keys_dir"

    # Verify ECDSA key was discovered
    ecdsa_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaPrime256v1"]
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in discovery.discovered_secrets
    assert ecdsa_secret.value == ecdsa_key_pem.decode("utf-8")
    assert ecdsa_secret.config_key == "secrets.keys_dir"


def test_individual_keys_discovery(tmp_path, rsa_key_pem, ecdsa_key_pem):
    """Test key discovery from individual keys configuration."""
    # Write RSA key file
    rsa_key_file = tmp_path / "rsa_key.pem"
    rsa_key_file.write_bytes(rsa_key_pem)

    # Convert ECDSA key to string for inline content
    ecdsa_pem_str = ecdsa_key_pem.decode("utf-8")

    # Create MAS config with individual keys
    mas_config = {
        "http": {"public_base": "https://auth.example.com"},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas"},
        "secrets": {
            "encryption": "my_encryption_key",
            "keys": [{"key_file": str(rsa_key_file)}, {"key": ecdsa_pem_str}],
        },
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
        },
    }

    # Test discovery
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Verify RSA key was discovered from file
    assert "matrixAuthenticationService.keys.rsa" in discovery.discovered_secrets
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].value == rsa_key_pem.decode("utf-8")
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].config_key == "secrets.keys.0.key_file"

    # Verify ECDSA key was discovered from inline content
    ecdsa_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaPrime256v1"]
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in discovery.discovered_secrets
    assert ecdsa_secret.value == ecdsa_key_pem.decode("utf-8")
    assert ecdsa_secret.config_key == "secrets.keys.1.key"


def test_mixed_key_sources(tmp_path, rsa_key_pem, ecdsa_key_pem):
    """Test key discovery with both keys_dir and individual keys."""
    # Create keys directory with ECDSA key
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    ecdsa_key_file = keys_dir / "ecdsa_key.pem"
    ecdsa_key_file.write_bytes(ecdsa_key_pem)

    # Write RSA key file for individual config
    rsa_key_file = tmp_path / "rsa_key.pem"
    rsa_key_file.write_bytes(rsa_key_pem)

    # Create MAS config with both keys_dir and individual keys
    mas_config = {
        "http": {"public_base": "https://auth.example.com"},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas"},
        "secrets": {
            "encryption": "my_encryption_key",
            "keys_dir": str(keys_dir),
            "keys": [{"key_file": str(rsa_key_file)}],
        },
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
        },
    }

    # Test discovery
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Verify both keys were discovered
    assert "matrixAuthenticationService.keys.rsa" in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in discovery.discovered_secrets

    # Individual keys should take precedence over directory keys
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].value == rsa_key_pem.decode("utf-8")
    assert discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"].config_key == "secrets.keys.0.key_file"
    ecdsa_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaPrime256v1"]
    assert ecdsa_secret.value == ecdsa_key_pem.decode("utf-8")
    assert ecdsa_secret.config_key == "secrets.keys_dir"


def test_no_keys_config(basic_mas_config):
    """Test that missing keys don't cause errors and are handled appropriately."""
    # Use basic config without any keys
    mas_config = basic_mas_config.copy()

    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Original key types should be marked for initialization since they're not required
    assert "matrixAuthenticationService.keys.rsa" in discovery.init_by_ess_secrets
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in discovery.init_by_ess_secrets

    # New key types should NOT be marked for initialization (they're optional)
    assert "matrixAuthenticationService.keys.ecdsaSecp256k1" not in discovery.init_by_ess_secrets
    assert "matrixAuthenticationService.keys.ecdsaSecp384r1" not in discovery.init_by_ess_secrets

    # Should not be in discovered secrets
    assert "matrixAuthenticationService.keys.rsa" not in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" not in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaSecp256k1" not in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaSecp384r1" not in discovery.discovered_secrets


def test_all_key_types_discovery(
    tmp_path, rsa_key_pem, ecdsa_key_pem, ecdsa_secp256k1_key_pem, ecdsa_secp384r1_key_pem
):
    """Test discovery of all supported key types from keys_dir."""
    # Create keys directory
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    # Write all key types
    (keys_dir / "rsa_key.pem").write_bytes(rsa_key_pem)
    (keys_dir / "ecdsa_prime256v1_key.pem").write_bytes(ecdsa_key_pem)
    (keys_dir / "ecdsa_secp256k1_key.pem").write_bytes(ecdsa_secp256k1_key_pem)
    (keys_dir / "ecdsa_secp384r1_key.pem").write_bytes(ecdsa_secp384r1_key_pem)

    # Create MAS config with keys_dir
    mas_config = {
        "http": {"public_base": "https://auth.example.com"},
        "database": {"uri": "postgresql://mas:mas_password@postgres:5432/mas"},
        "secrets": {"encryption": "my_encryption_key", "keys_dir": str(keys_dir)},
        "matrix": {
            "homeserver": "test.example.com",
            "secret": "synapse_shared_secret_abcdef",
        },
    }

    # Test discovery
    mas_secrets = MASSecretDiscovery()
    discovery = SecretDiscovery(mas_secrets, logging.getLogger(), "mas.yaml")
    discovery.discover_secrets(mas_config)

    # Verify all key types were discovered
    assert "matrixAuthenticationService.keys.rsa" in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaPrime256v1" in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaSecp256k1" in discovery.discovered_secrets
    assert "matrixAuthenticationService.keys.ecdsaSecp384r1" in discovery.discovered_secrets

    # Verify key values
    rsa_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.rsa"]
    ecdsa_prime256v1_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaPrime256v1"]
    ecdsa_secp256k1_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaSecp256k1"]
    ecdsa_secp384r1_secret = discovery.discovered_secrets["matrixAuthenticationService.keys.ecdsaSecp384r1"]

    assert rsa_secret.value == rsa_key_pem.decode("utf-8")
    assert ecdsa_prime256v1_secret.value == ecdsa_key_pem.decode("utf-8")
    assert ecdsa_secp256k1_secret.value == ecdsa_secp256k1_key_pem.decode("utf-8")
    assert ecdsa_secp384r1_secret.value == ecdsa_secp384r1_key_pem.decode("utf-8")

    # Verify config keys
    for secret_key in discovery.discovered_secrets:
        if secret_key.startswith("matrixAuthenticationService.keys."):
            assert discovery.discovered_secrets[secret_key].config_key == "secrets.keys_dir"
