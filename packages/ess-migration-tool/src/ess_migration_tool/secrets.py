# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Secret discovery service that handles all secret discovery functionality.
"""

import logging
from dataclasses import dataclass, field

from .interfaces import SecretDiscoveryStrategy
from .models import DiscoverableSecret, DiscoveredSecret, DiscoveredSecretTracking, GlobalOptions, SecretConfig
from .rich_output import print_section
from .utils import (
    find_matching_schema_key,
    get_nested_value,
    is_quiet_mode,
    is_wildcard_pattern,
    prompt_value,
)

logger = logging.getLogger("migration")


class SecretsError(Exception):
    """Base exception for secrets-related errors."""

    pass


@dataclass
class SecretDiscovery:
    """Complete implementation that handles all secret discovery functionality."""

    strategy: SecretDiscoveryStrategy = field(init=True)  # Strategy for component-specific secret discovery
    pretty_logger: logging.Logger = field(init=True)
    source_file: str = field(init=True)  # Source configuration file name
    global_options: GlobalOptions = field(init=True)  # Global migration options
    secret_tracking: DiscoveredSecretTracking = field(init=True)  # Global tracking of discovered secrets

    discovered_secrets: dict[str, DiscoveredSecret] = field(default_factory=dict)  # Secrets with source tracking
    init_by_ess_secrets: list[str] = field(default_factory=list)  # Secrets to be initialized by ESS
    missing_required_secrets: list[tuple[DiscoveredSecret, str | None]] = field(
        default_factory=list
    )  # (DiscoveredSecret, error_message) for required but missing/failed secrets

    def discover_secrets(self, config_data: dict) -> None:
        """Discover secrets from configuration data."""
        logging.info(f"Discovering {self.strategy.secret_name} secrets from configuration")

        # Common discovery using strategy's schema
        self._discover_secrets_from_schema(config_data)

        # Component-specific secret discovery (e.g., for MAS keys)
        component_secrets, component_failures = self.strategy.discover_component_specific_secrets(
            self.source_file, config_data
        )
        for secret_key, discovered_secret in component_secrets.items():
            # Check for exact match or wildcard pattern match
            matching_schema_key = find_matching_schema_key(secret_key, self.strategy.ess_secret_schema)
            if matching_schema_key is None:
                raise RuntimeError(f"Discovered component-specific secret '{secret_key}' not found in schema")
            # Get the precedence flag from the schema
            discoverable_secret = self.strategy.ess_secret_schema[matching_schema_key]
            # Add the discovered secret
            self.discovered_secrets[secret_key] = discovered_secret
            # Register with global tracking
            self.secret_tracking.add_source(
                secret_key=secret_key,
                strategy_name=self.strategy.secret_name,
                value=discovered_secret.value,
                source_path=discovered_secret.config_key,
                takes_precedence=discoverable_secret.takes_precedence_if_duplicates,
            )

        # Process component-specific discovery failures
        for discovered_secret, error_message in component_failures:
            secret_key = discovered_secret.secret_key

            # Find matching schema key (could be wildcard pattern)
            matching_schema_key = find_matching_schema_key(secret_key, self.strategy.ess_secret_schema)
            if matching_schema_key is None:
                logger.warning(f"Component-specific failed secret '{secret_key}' not found in schema: {error_message}")
                continue

            # Check if this secret is required based on the matching schema
            discoverable_secret = self.strategy.ess_secret_schema[matching_schema_key]
            if discoverable_secret.optional:
                # Optional secrets are ignored if not found
                continue
            elif discoverable_secret.init_if_missing_from_source_cfg:
                self.init_by_ess_secrets.append(secret_key)
            else:
                self.missing_required_secrets.append((discovered_secret, error_message))

    def _discover_secrets_from_schema(self, config_data: dict) -> None:
        """Common discovery logic using the strategy's ess_secret_schema."""
        for secret_key, discoverable_secret in self.strategy.ess_secret_schema.items():
            # Skip wildcard patterns - these are handled by discover_component_specific_secrets
            if is_wildcard_pattern(secret_key):
                continue

            # Skip if already discovered (e.g., by component-specific discovery)
            if secret_key in self.discovered_secrets:
                continue

            discovery_config = discoverable_secret.discovery

            # If discovery is None, this secret cannot be discovered from config files
            # Skip directly to missing secret handling
            if discovery_config is None:
                self._handle_missing_secret(secret_key, discoverable_secret, None)
                continue

            # Try to discover the secret from config
            discovered_value, error_msg = self._try_discover_from_config(secret_key, discovery_config, config_data)

            if discovered_value is not None:
                self._add_discovered_secret(
                    secret_key,
                    discovery_config,
                    discovered_value,
                    takes_precedence=discoverable_secret.takes_precedence_if_duplicates,
                )
                continue

            # Secret was not discovered from config - handle missing case
            self._handle_missing_secret(secret_key, discoverable_secret, error_msg)

    def _try_discover_from_config(
        self,
        secret_key: str,
        discovery_config: SecretConfig,
        config_data: dict,
    ) -> tuple[str | None, str | None]:
        """
        Try to discover a secret value from configuration.

        Args:
            secret_key: The ESS secret key
            discovery_config: The discovery configuration (SecretConfig)
            config_data: The source configuration data

        Returns:
            Tuple of (discovered_value, error_msg) where:
            - discovered_value: The secret value if found, None otherwise
            - error_msg: Error message if file reading failed, None otherwise
        """
        discovered_value = None
        error_msg: str | None = None

        # Try inline value first
        if discovery_config.config_inline:
            value = get_nested_value(config_data, discovery_config.config_inline)
            if value is not None:
                discovered_value = value
                logging.info(f"Found direct value for {secret_key}")

        # Try file path if inline value wasn't found
        if discovered_value is None and discovery_config.config_path:
            file_path = get_nested_value(config_data, discovery_config.config_path)
            if file_path is not None:
                try:
                    with open(file_path) as f:
                        discovered_value = f.read()
                    logging.info(f"Found file value for {secret_key}")
                except FileNotFoundError:
                    logger.warning(f"File not found: {file_path}")
                    error_msg = f"File not found: {file_path}"
                except PermissionError:
                    logger.warning(f"Permission denied when reading file: {file_path}")
                    error_msg = f"Permission denied reading file: {file_path}"

        # Apply transformer if available and we have a value
        if discovered_value is not None and discovery_config.transformer is not None:
            try:
                discovered_value = discovery_config.transformer(discovered_value)
                logger.info(f"Applied transformer to {secret_key}")
            except Exception as e:
                logger.warning(f"Failed to apply transformer for {secret_key}: {e}")
                discovered_value = None

        return discovered_value, error_msg

    def _add_discovered_secret(
        self,
        secret_key: str,
        discovery_config: SecretConfig,
        discovered_value: str,
        takes_precedence: bool = False,
    ) -> None:
        """Add a discovered secret to the discovered_secrets dictionary."""
        config_key = discovery_config.config_inline or discovery_config.config_path
        if not config_key:
            raise RuntimeError(f"Missing configuration path for {secret_key}")

        discovered_secret = DiscoveredSecret(
            source_file=self.source_file,
            secret_key=secret_key,
            config_key=config_key,
            value=discovered_value,
        )
        self.discovered_secrets[secret_key] = discovered_secret
        # Register with global tracking
        self.secret_tracking.add_source(
            secret_key=secret_key,
            strategy_name=self.strategy.secret_name,
            value=discovered_value,
            source_path=config_key,
            takes_precedence=takes_precedence,
        )

    def _handle_missing_secret(
        self,
        secret_key: str,
        discoverable_secret: DiscoverableSecret,
        error_msg: str | None,
    ) -> None:
        """
        Handle a secret that was not discovered from config.

        Based on the secret's configuration, either:
        - Ignore it (if optional)
        - Add to init_by_ess_secrets (if init_if_missing_from_source_cfg)
        - Add to missing_required_secrets (if required)
        """
        # Check if already discovered by another strategy
        if self.secret_tracking.is_discovered(secret_key):
            # Don't add to missing_required_secrets or init_by_ess_secrets
            return

        # Optional secrets are ignored if not found
        if discoverable_secret.optional:
            return

        discovery_config = discoverable_secret.discovery

        # Determine config_key for the missing secret
        if discovery_config is None:
            config_key_for_missing = None
        else:
            config_key_for_missing = (
                discovery_config.config_path
                if error_msg
                else discovery_config.config_inline or discovery_config.config_path
            )

        # If there's no way to discover this secret from the config,
        # it can only be initialized by ESS or discovered via component-specific discovery
        if config_key_for_missing is None:
            if discoverable_secret.init_if_missing_from_source_cfg:
                self.init_by_ess_secrets.append(secret_key)
            # Don't add to missing_required_secrets - component-specific discovery will handle these
            return

        # Secret has a config path but wasn't found - create a placeholder
        discovered_secret_still_missing = DiscoveredSecret(
            source_file=self.source_file,
            secret_key=secret_key,
            config_key=config_key_for_missing,
            value="",
        )

        if discoverable_secret.init_if_missing_from_source_cfg:
            self.init_by_ess_secrets.append(secret_key)
        else:
            self.missing_required_secrets.append((discovered_secret_still_missing, error_msg))

    def validate_required_secrets(self) -> None:
        """Validate that all required secrets are present."""
        if self.missing_required_secrets:
            missing_list = ", ".join(ds.secret_key for ds, _ in self.missing_required_secrets)
            raise SecretsError(f"Missing required {self.strategy.secret_name} secrets: {missing_list}")
        logging.info(f"All required {self.strategy.secret_name} secrets are present")

    def prompt_for_missing_secrets(self) -> None:
        """Prompt user to provide missing required secrets."""
        if not self.missing_required_secrets:
            return

        # Check if quiet mode is enabled
        if is_quiet_mode(self.pretty_logger):
            missing_list = ", ".join(ds.secret_key for ds, _ in self.missing_required_secrets)
            raise SecretsError(
                f"Missing required {self.strategy.secret_name} secrets in quiet mode: {missing_list}. "
                "Cannot prompt for secrets when --quiet is enabled."
            )

        component_name = self.strategy.secret_name.upper()
        print_section(f"🔐 {component_name} SECRETS REQUIRED FOR MIGRATION", logger=self.pretty_logger)
        self.pretty_logger.info(f"The following {component_name} secrets are required but could not be automatically")
        self.pretty_logger.info("discovered from your configuration files. Please provide them:")

        for discovered_secret, error_message in self.missing_required_secrets[:]:
            secret_key = discovered_secret.secret_key
            config_key = discovered_secret.config_key

            # Find matching schema key (supports wildcard patterns)
            matching_schema_key = find_matching_schema_key(secret_key, self.strategy.ess_secret_schema)
            assert matching_schema_key is not None
            discoverable_secret = self.strategy.ess_secret_schema[matching_schema_key]

            self.pretty_logger.info(f"📝 {discoverable_secret.description}")
            self.pretty_logger.info(f"   Secret path: {secret_key}")

            # Add failure reason if available
            if error_message:
                self.pretty_logger.info(f"   ⚠️  {error_message}")
                if "Permission denied" in error_message:
                    self.pretty_logger.info("   💡 Use elevated privileges to read this file")

            if not config_key:
                raise RuntimeError(f"Missing configuration path for {secret_key}")

            value = prompt_value(
                self.pretty_logger,
                "Please paste the secret value:",
            )
            self.discovered_secrets[secret_key] = DiscoveredSecret(
                source_file=self.source_file,
                secret_key=secret_key,
                config_key=config_key,
                value=value,
            )
            # Remove from missing_required_secrets after successful prompt
            self.missing_required_secrets.remove((discovered_secret, error_message))
            self.pretty_logger.info(f"   ✅ Secret stored for {secret_key}")

        self.pretty_logger.info(f"\n✅ All required {component_name} secrets have been provided")
        self.pretty_logger.info("=" * 60)
