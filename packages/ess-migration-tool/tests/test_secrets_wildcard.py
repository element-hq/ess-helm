# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Generic tests for the secret discovery wildcard mechanism.

Tests that the wildcard pattern matching infrastructure works correctly
for future features that use wildcard notation in ess_secrets_schema.
"""

import logging

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
        self, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], dict[str, str]]:
        """
        Discover secrets with wildcard-expanded keys.

        This simulates a strategy that discovers multiple certificates
        and expands the wildcard pattern into concrete keys.

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
        """
        discovered: dict[str, DiscoveredSecret] = {}
        failed: dict[str, str] = {}

        # Simulate discovering certificate values from config
        certs = config_data.get("certificates", [])
        for i, cert in enumerate(certs):
            if "value" in cert:
                secret_key = f"certificates.{i}.value"
                discovered[secret_key] = DiscoveredSecret(
                    source_file="test.yaml",
                    secret_key=secret_key,
                    config_key=f"certificates.{i}.value",
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
        self, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], dict[str, str]]:
        """
        Discover secrets with wildcard-expanded keys, including some failures.

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
        """
        discovered: dict[str, DiscoveredSecret] = {}
        failed: dict[str, str] = {}

        # Simulate discovering certificate values from config (all succeed)
        certs = config_data.get("certificates", [])
        for i, cert in enumerate(certs):
            if "value" in cert:
                secret_key = f"certificates.{i}.value"
                discovered[secret_key] = DiscoveredSecret(
                    source_file="test.yaml",
                    secret_key=secret_key,
                    config_key=f"certificates.{i}.value",
                    value=cert["value"],
                )

        # Simulate some key failures
        keys = config_data.get("keys", [])
        for i, key in enumerate(keys):
            secret_key = f"keys.{i}.private"
            # Simulate failure for keys without "private" field
            if "private" not in key:
                failed[secret_key] = f"Failed to read key file for keys.{i}.private"
            else:
                discovered[secret_key] = DiscoveredSecret(
                    source_file="test.yaml",
                    secret_key=secret_key,
                    config_key=f"keys.{i}.private",
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
    assert "keys.0.private" in discovery.missing_required_secrets
    assert "keys.0.private" in discovery.secret_discovery_failures

    # Verify failure message
    assert "Failed to read key file" in discovery.secret_discovery_failures["keys.0.private"]

    # Use monkeypatch to provide input for the prompt
    monkeypatch.setattr("builtins.input", lambda _: "my-secret-value")

    # Call prompt_for_missing_secrets (should prompt for the missing secret)
    discovery.prompt_for_missing_secrets()

    # After prompting, the secret should be discovered
    assert "keys.0.private" in discovery.discovered_secrets
    assert discovery.discovered_secrets["keys.0.private"].value == "my-secret-value"
    assert "keys.0.private" not in discovery.missing_required_secrets
