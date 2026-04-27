# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Generic tests for the secret discovery wildcard mechanism.

Tests that the wildcard pattern matching infrastructure works correctly
for future features that use wildcard notation in ess_secrets_schema.
"""

import logging
from typing import Any

import pytest
from ess_migration_tool.interfaces import SecretDiscoveryStrategy
from ess_migration_tool.migration import ConfigValueTransformer
from ess_migration_tool.models import DiscoveredSecret, GlobalOptions, Secret, SecretConfig
from ess_migration_tool.secrets import SecretDiscovery


class MockWildcardStrategy(SecretDiscoveryStrategy):
    """Mock strategy for testing wildcard secret discovery."""

    def __init__(self, global_options: GlobalOptions, component_config: dict):
        self.global_options = global_options
        self.component_config = component_config

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Schema with wildcard pattern for certificates."""
        return {
            "certificates.*.value": SecretConfig(
                init_if_missing_from_source_cfg=False,
                description="Certificate value",
                config_inline=None,
                config_path=None,
            ),
        }

    @property
    def secret_name(self) -> str:
        return "test-component"

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict[str, Any]
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Discover secrets with wildcard-expanded keys.

        This simulates a strategy that discovers multiple certificates
        and expands the wildcard pattern into concrete keys.

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
        """
        discovered: dict[str, DiscoveredSecret] = {}
        failed: list[tuple[DiscoveredSecret, str]] = []

        # Simulate discovering certificate values from config
        certs: list[dict[str, Any]] = config_data.get("certificates", [])
        for i, cert in enumerate(certs):
            if "value" in cert:
                ess_secret_key = f"certificates.{i}.value"  # ESS path
                source_config_key = f"source.certificates.{i}.value"  # Source path - different
                discovered[ess_secret_key] = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=ess_secret_key,
                    config_key=source_config_key,
                    value=cert["value"],
                )

        return (discovered, failed)


def test_wildcard_secret_discovery_and_injection():
    """
    Test the complete wildcard mechanism:
    1. Strategy defines wildcard schema pattern
    2. Component-specific discovery expands to concrete keys
    3. SecretDiscovery validates using find_matching_schema_key
    4. handle_secrets creates proper array structure with credential schema
    """
    # Setup test data
    component_config = {
        "certificates": [
            {"value": "certificate_value_0"},
            {"value": "certificate_value_1"},
            {"value": "certificate_value_2"},
        ],
    }

    global_options = GlobalOptions()
    strategy = MockWildcardStrategy(global_options, component_config)
    discovery = SecretDiscovery(
        strategy=strategy,
        pretty_logger=logging.getLogger(),
        source_file="test.yaml",
        global_options=global_options,
    )

    # Discover secrets (this should work with wildcards)
    discovery.discover_secrets(component_config)

    # Verify wildcard-expanded secrets were discovered
    assert "certificates.0.value" in discovery.discovered_secrets
    assert "certificates.1.value" in discovery.discovered_secrets
    assert "certificates.2.value" in discovery.discovered_secrets

    # Use actual handle_secrets to inject credential configs
    secrets_list: list[Secret] = []
    transformer = ConfigValueTransformer(
        pretty_logger=logging.getLogger(),
        ess_config={},
    )

    transformer.handle_secrets(discovery, secrets_list)

    ess_config = transformer.ess_config

    # Verify Kubernetes Secret was created
    assert len(secrets_list) == 1
    secret = secrets_list[0]
    assert secret.name == "imported-test-component"

    # Verify all discovered secrets are in the Kubernetes Secret data
    assert "certificates.0.value" in secret.data
    assert "certificates.1.value" in secret.data
    assert "certificates.2.value" in secret.data

    # Verify array structure was created correctly via set_nested_value
    assert "certificates" in ess_config
    assert isinstance(ess_config["certificates"], list)
    assert len(ess_config["certificates"]) >= 3

    # Check that each certificate has the credential config at the right index
    assert ess_config["certificates"][0]["value"] == {
        "secret": "imported-test-component",
        "secretKey": "certificates.0.value",
    }
    assert ess_config["certificates"][1]["value"] == {
        "secret": "imported-test-component",
        "secretKey": "certificates.1.value",
    }
    assert ess_config["certificates"][2]["value"] == {
        "secret": "imported-test-component",
        "secretKey": "certificates.2.value",
    }


class MockWildcardStrategyWithFailures(SecretDiscoveryStrategy):
    """Mock strategy for testing wildcard secret discovery with failures."""

    def __init__(self, global_options: GlobalOptions, component_config: dict):
        self.global_options = global_options
        self.component_config = component_config

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Schema with wildcard pattern for certificates and keys."""
        return {
            "certificates.*.value": SecretConfig(
                init_if_missing_from_source_cfg=False,
                description="Certificate value",
                config_inline=None,
                config_path=None,
            ),
            "keys.*.private": SecretConfig(
                init_if_missing_from_source_cfg=False,
                description="Private key",
                config_inline="keys.*.private",
                config_path=None,
                optional=False,  # Required
            ),
        }

    @property
    def secret_name(self) -> str:
        return "test-component"

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict[str, Any]
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Discover secrets with wildcard-expanded keys, including some failures.

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
        """
        discovered: dict[str, DiscoveredSecret] = {}
        failed: list[tuple[DiscoveredSecret, str]] = []

        # Simulate discovering certificate values from config (all succeed)
        certs: list[dict[str, Any]] = config_data.get("certificates", [])
        for i, cert in enumerate(certs):
            if "value" in cert:
                ess_secret_key = f"certificates.{i}.value"
                source_config_key = f"source.certificates.{i}.value"
                discovered[ess_secret_key] = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=ess_secret_key,
                    config_key=source_config_key,
                    value=cert["value"],
                )

        # Simulate some key failures
        keys: list[dict[str, Any]] = config_data.get("keys", [])
        for i, key in enumerate(keys):
            ess_secret_key = f"keys.{i}.private"
            source_config_key = f"keys.{i}.private"
            # Simulate failure for keys without "private" field
            if "private" not in key:
                failed_secret = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=ess_secret_key,
                    config_key=source_config_key,
                    value="",
                )
                failed.append((failed_secret, f"Failed to read key file for keys.{i}.private"))
            else:
                discovered[ess_secret_key] = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=ess_secret_key,
                    config_key=source_config_key,
                    value=key["private"],
                )

        return (discovered, failed)


def test_wildcard_secret_prompt_for_missing(monkeypatch: pytest.MonkeyPatch):
    """
    Test that missing wildcard secrets can be prompted for and stored correctly.

    Uses monkeypatch to simulate user input for the missing secret.
    """
    component_config: dict = {
        "keys": [
            {},  # This one will fail and need prompting
        ],
    }

    global_options = GlobalOptions()
    strategy = MockWildcardStrategyWithFailures(global_options, component_config)

    discovery = SecretDiscovery(
        strategy=strategy,
        pretty_logger=logging.getLogger("test"),
        source_file="test.yaml",
        global_options=global_options,
    )

    # Discover secrets
    discovery.discover_secrets(component_config)

    # The failed secret should be in missing_required_secrets
    failed_secret_keys = [ds.secret_key for ds, _ in discovery.missing_required_secrets]
    assert "keys.0.private" in failed_secret_keys

    # Verify failure message
    failure_tuples = [t for t in discovery.missing_required_secrets if t[0].secret_key == "keys.0.private"]
    assert len(failure_tuples) == 1
    error_message = failure_tuples[0][1]
    assert error_message is not None
    assert "Failed to read key file" in error_message

    # Use monkeypatch to provide input for the prompt
    monkeypatch.setattr("builtins.input", lambda _: "my-secret-value")

    # Call prompt_for_missing_secrets (should prompt for the missing secret)
    discovery.prompt_for_missing_secrets()

    # After prompting, the secret should be discovered
    assert "keys.0.private" in discovery.discovered_secrets
    assert discovery.discovered_secrets["keys.0.private"].value == "my-secret-value"
    # Check that the secret is no longer in missing_required_secrets
    missing_secret_keys = {ds.secret_key for ds, _ in discovery.missing_required_secrets}
    assert "keys.0.private" not in missing_secret_keys
