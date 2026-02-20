# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Secret discovery service that handles all secret discovery functionality.
"""

import logging
from dataclasses import dataclass, field

from .interfaces import SecretDiscoveryStrategy
from .models import DiscoveredSecret
from .utils import get_nested_value


class SecretsError(Exception):
    """Base exception for secrets-related errors."""

    pass


@dataclass
class SecretDiscovery:
    """Complete implementation that handles all secret discovery functionality."""

    strategy: SecretDiscoveryStrategy = field(init=True)  # Strategy for component-specific secret discovery
    pretty_logger: logging.Logger = field(init=True)
    source_file: str = field(init=True)  # Source configuration file name

    discovered_secrets: dict[str, DiscoveredSecret] = field(default_factory=dict)  # Secrets with source tracking
    init_by_ess_secrets: list[str] = field(default_factory=list)  # Secrets to be initialized by ESS
    missing_required_secrets: list[str] = field(default_factory=list)  # Secrets missing from configuration

    def discover_secrets(self, config_data: dict) -> None:
        """Discover secrets from configuration data."""
        logging.info(f"Discovering {self.strategy.component_name} secrets from configuration")

        # Common discovery using strategy's schema
        self._discover_secrets_from_schema(config_data)

    def _discover_secrets_from_schema(self, config_data: dict) -> None:
        """Common discovery logic using the strategy's ess_secret_schema."""
        for secret_key, secret_config in self.strategy.ess_secret_schema.items():
            discovered_value = None

            if secret_config.config_inline:
                # Direct value
                value = get_nested_value(config_data, secret_config.config_inline)
                if value is not None:
                    discovered_value = value
                    logging.info(f"Found direct value for {secret_key}")

            # Also try file path if direct value wasn't found
            if discovered_value is None and secret_config.config_path:
                # From file
                file_path = get_nested_value(config_data, secret_config.config_path)
                if file_path is not None:
                    try:
                        with open(file_path) as f:
                            discovered_value = f.read()
                        logging.info(f"Found file value for {secret_key}")
                    except FileNotFoundError:
                        logging.warning(f"File not found: {file_path}")

            # Apply transformer if available and we have a value
            if discovered_value is not None and secret_config.transformer is not None:
                try:
                    discovered_value = secret_config.transformer(discovered_value)
                    logging.info(f"Applied transformer to {secret_key}")
                except Exception as e:
                    logging.warning(f"Failed to apply transformer for {secret_key}: {e}")
                    discovered_value = None

            if discovered_value is not None:
                # Track the source information
                config_key = secret_config.config_inline or secret_config.config_path
                if not config_key:
                    raise RuntimeError(f"Missing configuration path for {secret_key}")
                discovered_secret = DiscoveredSecret(
                    source_file=self.source_file, secret_key=secret_key, config_key=config_key, value=discovered_value
                )

                self.discovered_secrets[secret_key] = discovered_secret

            if secret_key not in self.discovered_secrets:
                if secret_config.init_if_missing_from_source_cfg:
                    self.init_by_ess_secrets.append(secret_key)
                else:
                    self.missing_required_secrets.append(secret_key)

    def validate_required_secrets(self) -> None:
        """Validate that all required secrets are present."""
        if self.missing_required_secrets:
            missing_list = ", ".join(self.missing_required_secrets)
            raise SecretsError(f"Missing required {self.strategy.component_name} secrets: {missing_list}")
        logging.info(f"All required {self.strategy.component_name} secrets are present")

    def prompt_for_missing_secrets(self) -> None:
        """Prompt user to provide missing required secrets."""
        if not self.missing_required_secrets:
            return
        component_name = self.strategy.component_name.upper()
        self.pretty_logger.info("\n" + "=" * 60)
        self.pretty_logger.info(f"🔐 {component_name} SECRETS REQUIRED FOR MIGRATION")
        self.pretty_logger.info("=" * 60)
        self.pretty_logger.info(f"The following {component_name} secrets are required but could not be automatically")
        self.pretty_logger.info("discovered from your configuration files. Please provide them:")

        for secret_key in self.missing_required_secrets[:]:
            secret_info = self.strategy.ess_secret_schema.get(secret_key)
            assert secret_info is not None

            self.pretty_logger.info(f"📝 {secret_info.description}")
            self.pretty_logger.info(f"   Secret path: {secret_key}")

            # The config key that will be injected in the configuration is preferably the path to the secret
            # But we fallback to the config_inline in needed
            config_key = self.strategy.ess_secret_schema[secret_key].config_path
            if not config_key:
                config_key = self.strategy.ess_secret_schema[secret_key].config_inline
            if not config_key:
                raise RuntimeError(f"Missing configuration path for {secret_key}")

            while True:
                try:
                    value = input("   Please paste the secret value: ").strip()
                    if value:
                        self.discovered_secrets[secret_key] = DiscoveredSecret(
                            source_file=self.source_file,
                            secret_key=secret_key,
                            config_key=config_key,
                            value=value,
                        )
                        self.missing_required_secrets.remove(secret_key)
                        self.pretty_logger.info(f"   ✅ Secret stored for {secret_key}")
                        break
                    else:
                        self.pretty_logger.info("   ❌ Value cannot be empty. Please try again.")
                except KeyboardInterrupt as err:
                    self.pretty_logger.info("\n   ❌ Operation cancelled by user")
                    raise SecretsError("User cancelled secret input") from err
                except EOFError as err:
                    self.pretty_logger.info("\n   ❌ End of input reached")
                    raise SecretsError("End of input reached during secret prompt") from err

        self.pretty_logger.info(f"\n✅ All required {component_name} secrets have been provided")
        self.pretty_logger.info("=" * 60)
