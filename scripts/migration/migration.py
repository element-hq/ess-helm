# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration service.
"""

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .extra_files import ExtraFilesDiscovery
from .interfaces import ExtraFilesDiscoveryStrategy, MigrationStrategy, SecretDiscoveryStrategy
from .models import ConfigMap, DiscoveredExtraFile, DiscoveredSecret, MigrationInput, Secret
from .secrets import SecretDiscovery
from .utils import (
    get_nested_value,
    remove_nested_value,
    set_nested_value,
    yaml_dump_with_pipe_for_multiline,
)

logger = logging.getLogger("migration")


@dataclass
class TransformationSpec:
    """
    Specification for a configuration transformation.

    Defines how to map from a source configuration path to a target ESS path.
    """

    src_key: str  # Source configuration path
    target_key: str  # Target ESS configuration path
    required: bool = True  # Whether this transformation is required
    transformer: Callable[[Any], Any] | None = None  # Optional transformation function


@dataclass
class TransformationResult:
    """
    Result of a configuration transformation.

    Contains the transformation specification along with the actual value.
    """

    spec: TransformationSpec  # Transformation specification
    value: Any  # Transformed value


@dataclass
class ConfigValueTransformer:
    """
    Enhanced transformer for configuration values that handles the complete
    transformation from source configuration to ESS format using explicit
    source and target paths.
    """

    pretty_logger: logging.Logger | None = field(default=None)  # Pretty logger
    results: list[TransformationResult] = field(default_factory=list)  # List of transformation results
    tracked_values: list[str] = field(default_factory=list)  # Source paths that have been processed
    ess_config: dict[str, Any] = field(default_factory=dict)  # Target ESS configuration dictionary

    def transform_from_config(self, source_config: dict[str, Any], transformations: list[TransformationSpec]) -> None:
        """
        Transform values from a source configuration using explicit source and target path mappings.

        Args:
            source_config: Source configuration dictionary
            transformations: List of TransformationSpec objects
        """
        for transformation in transformations:
            # Get the value from the source configuration
            value = get_nested_value(source_config, transformation.src_key)

            if value is not None:
                # Apply transformer function if provided
                transformed_value = value
                if transformation.transformer is not None:
                    transformed_value = transformation.transformer(self.pretty_logger, value)

                # Track the source path if not already tracked
                if transformation.src_key not in self.tracked_values:
                    self.tracked_values.append(transformation.src_key)

                # Create TransformationResult using the current transformation spec
                result = TransformationResult(spec=transformation, value=transformed_value)
                self.results.append(result)

                # Set the transformed value in the ESS config
                set_nested_value(self.ess_config, transformation.target_key, transformed_value)
            elif transformation.required:
                # If the transformation is required but the value is missing, raise an error
                raise MigrationError(
                    f"Required configuration value '{transformation.src_key}' is missing from the source configuration"
                )

    def get_component_config(self, component_key: str) -> dict[str, Any]:
        """
        Get the configuration for a specific component.

        Args:
            component_key: The component key (e.g., "synapse", "matrixAuthenticationService")

        Returns:
            Dictionary with the component configuration, or empty dict if not found
        """
        return self.ess_config.get(component_key, {})

    def filter_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Create a filtered copy of the config that removes tracked values.

        Args:
            config: Original configuration

        Returns:
            Filtered configuration with tracked values removed
        """
        import copy

        filtered_config = copy.deepcopy(config)

        for source_path in self.tracked_values:
            remove_nested_value(filtered_config, source_path)

        return filtered_config

    def add_additional_config_to_component(self, component_key: str, source_config: dict[str, Any]) -> None:
        """
        Add filtered additional configurations to a specific component in the ESS config.

        This method filters the source configuration to remove values that are passed to ESS,
        then adds the filtered configuration to the component's 'additional' section.

        Args:
            component_key: The component key (e.g., "synapse", "matrixAuthenticationService")
            source_config: Original configuration to filter and add
        """
        # Get or create the component config in the ESS config
        component_config = self.ess_config.setdefault(component_key, {})

        # Filter the source config to remove tracked values
        filtered_config = self.filter_config(source_config)

        # Add to additional section if there's anything to add
        if filtered_config:
            component_config["additional"] = {
                "00-imported.yaml": {"config": yaml_dump_with_pipe_for_multiline(filtered_config)}
            }

    def handle_secrets(
        self,
        secret_discovery: SecretDiscovery,
        component_root_key: str,
        secrets_list: list[Secret],
    ) -> None:
        """
        Handle secrets for component using SecretDiscovery.

        Args:
            config: Configuration to analyze for secrets
            secret_service: SecretDiscoveryService instance
            component_root_key: Name of the component (synapse or mas)
            secrets_list: List to append created secrets to

        Returns:
            ESS configuration dictionary with credential schema
        """
        # Skip if secret_service is None or no secrets discovered
        if secret_discovery is None or not secret_discovery.discovered_secrets:
            return

        # Create a Kubernetes Secret containing all discovered secrets
        # Convert component_root_key to kebab-case for the secret name
        # Replace camelCase with kebab-case (e.g., "matrixAuthenticationService" -> "matrix-authentication-service")
        kebab_case_name = component_root_key
        # Insert hyphens before uppercase letters and convert to lowercase
        kebab_case_name = "".join(["-" + c.lower() if c.isupper() else c for c in kebab_case_name]).lstrip("-")

        secret_name = f"imported-{kebab_case_name}"
        secret_data = {}

        for secret_key, discover_secret in secret_discovery.discovered_secrets.items():
            # Base64 encode the secret value for Kubernetes Secret
            encoded_value = base64.b64encode(discover_secret.value.encode("utf-8")).decode("utf-8")
            secret_data[secret_key] = encoded_value

        secret = Secret(name=secret_name, data=secret_data)
        secrets_list.append(secret)
        logging.info(
            f"Created Kubernetes Secret with {len(secret_discovery.discovered_secrets)}"
            f" secrets for {component_root_key}"
        )

        # Update ESS values to use credential schema instead of direct values
        # Use the ess_secret_schema to map secret keys to ESS configuration paths
        for secret_key, discover_secret in secret_discovery.discovered_secrets.items():
            # Convert secret key to credential schema format
            # Example: secret -> {"secret": "imported-synapse", "secretKey": "synapse.postgres.password"}
            credential_config = {"secret": secret.name, "secretKey": secret_key}

            # Get the secret configuration from the schema
            secret_config = secret_discovery.strategy.ess_secret_schema.get(secret_key)
            if secret_config is None:
                raise RuntimeError(f"No ESS configuration mapping found for secret key: {secret_key}")

            # Set the credential config in the ESS config under the component section
            set_nested_value(self.ess_config, discover_secret.secret_key, credential_config)

            # Track the config value that is being passed to ESS
            # We need to track the original config path so it gets filtered out later
            self.tracked_values.append(discover_secret.secret_key)


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    pass


@dataclass
class MigrationService:
    """Migration service."""

    input: MigrationInput = field(init=True)  # Migration input data
    pretty_logger: logging.Logger = field(init=True)  # Pretty logger
    ess_config: dict[str, Any] = field(init=True)  # Target ESS configuration
    migration: MigrationStrategy = field(init=True)  # Migration strategy
    extra_files_strategy: ExtraFilesDiscoveryStrategy = field(init=True)  # Extra files discovery service
    secret_discovery_strategy: SecretDiscoveryStrategy = field(init=True)  # Secret discovery service
    override_warnings: list[str] = field(default_factory=list)  # Warnings about overridden configurations
    init_by_ess_secrets: list[str] = field(default_factory=list)  # List of secrets that will be initialized by ESS
    discovered_secrets: list[DiscoveredSecret] = field(default_factory=list)  # List of discovered secrets
    discovered_extra_files: list[DiscoveredExtraFile] = field(default_factory=list)  # List of discovered secrets
    secrets: list[Secret] = field(default_factory=list)  # List of created Secrets
    configmaps: list[ConfigMap] = field(default_factory=list)  # List of created ConfigMaps
    override_configs: set[str] = field(default_factory=set)  # Set of configurations that are managed by ESS
    component_root_key: str = field(init=False)  # Root key for the component (e.g., 'synapse')
    config_to_ess_transformer: ConfigValueTransformer = field(default_factory=ConfigValueTransformer)  # Config

    def __post_init__(self):
        self.component_root_key = self.migration.component_root_key
        self.override_configs = self.migration.override_configs
        self.config_to_ess_transformer.ess_config = self.ess_config
        self.config_to_ess_transformer.pretty_logger = self.pretty_logger

    def _check_overrides(self, config: dict[str, Any]) -> None:
        """
        Check if the configuration contains any override configurations
        that are managed by ESS and cannot be overridden.

        Only shows overrides that are managed by ESS chart (no direct transformation).
        Settings with transformations are already shown in "Successfully migrated" section.

        Args:
            config: Configuration to check
        """
        override_warnings = []

        # Build set of transformed config paths for filtering
        transformed_configs = set()
        for transformation in self.migration.transformations:
            transformed_configs.add(transformation.src_key)

        # Use the filtered configuration (with migrated values removed) for override detection
        # This automatically excludes values that are tracked by the transformer,
        # including both regular transformations and secrets (which are added to tracked_values during handle_secrets)
        filtered_config = self.config_to_ess_transformer.filter_config(config)

        for override_config in self.override_configs:
            # Check if the override config path exists in the filtered configuration
            # and is managed by ESS chart (no direct transformation)
            if (
                get_nested_value(filtered_config, override_config) is not None
                and override_config not in transformed_configs
            ):
                override_warnings.append(
                    f"⚠️  '{override_config}' found in {self.component_root_key}.additional[\"00-imported.yaml\"].config"
                )

        if override_warnings:
            self.override_warnings.extend(override_warnings)
            logger.warning(f"{self.component_root_key} configuration contains ESS-managed overrides:")
            for warning in override_warnings:
                logger.warning(warning)

    def _update_config_with_mounted_file_paths(self, config: dict[str, Any]) -> None:
        """
        Update configuration to point to mounted file paths instead of original file paths.
        Uses the tracked reference paths to update only the exact locations where files were referenced.

        Args:
            config: Configuration dictionary to update
        """
        if not self.discovered_extra_files:
            return

        # Get the base mount path for the component
        base_mount_path = getattr(self.migration, "configmap_mount_path", f"/etc/{self.component_root_key}/extra")

        for extra_file in self.discovered_extra_files:
            # Get the original value for logging (we know it exists since we just parsed it)
            original_value = get_nested_value(config, extra_file.discovered_source_path.config_key)
            original_name = extra_file.discovered_source_path.source_path.name
            mounted_path = f"{base_mount_path}/{original_name}"
            set_nested_value(config, extra_file.discovered_source_path.config_key, mounted_path)
            logging.info(
                f"Updated config: {extra_file.discovered_source_path.config_key} = {original_value} -> {mounted_path}"
            )

    def _create_configmap_from_files(self, f, component_name: str) -> ConfigMap:
        """
        Create a single ConfigMap containing all extra files for a component.

        Args:
            file_paths: List of file paths to include in the ConfigMap
            component_name: Name of the component (synapse or mas)

        Returns:
            ConfigMap object containing all files
        """
        configmap_data = {}

        for extra_file in self.discovered_extra_files:
            if extra_file.cleartext:
                # Use the file name as the key in the ConfigMap
                file_name = Path(extra_file.discovered_source_path.source_path).name
                configmap_data[file_name] = extra_file.content.decode("utf-8")

        # Create a single ConfigMap name for the component
        configmap_name = f"{component_name}-extra-files"

        return ConfigMap(
            name=configmap_name,
            data=configmap_data,
        )

    def migrate(self) -> None:
        """
        Perform migration using the injected strategy.

        Migration steps:
        1. Enable component
        1. Apply component transformations
        2. Check for override configurations
        3. Add filtered additional configurations
        """
        # Step 1: Discover secrets
        secret_discovery = SecretDiscovery(
            strategy=self.secret_discovery_strategy,
            source_file=self.input.config_path,
            pretty_logger=self.pretty_logger,
        )
        secret_discovery.discover_secrets(self.input.config)
        # Prompt for missing secrets then validate
        secret_discovery.prompt_for_missing_secrets()
        secret_discovery.validate_required_secrets()
        self.discovered_secrets = list(secret_discovery.discovered_secrets.values())
        self.init_by_ess_secrets = secret_discovery.init_by_ess_secrets

        # Step 2: Discover extra files
        extra_files_discovery = ExtraFilesDiscovery(
            source_file=self.input.config_path,
            strategy=self.extra_files_strategy,
            secrets_strategy=self.secret_discovery_strategy,
            pretty_logger=self.pretty_logger,
        )
        extra_files_discovery.discover_extra_files_from_config(self.input.config)
        # Prompt for missing files then validate
        extra_files_discovery.prompt_for_missing_files()
        extra_files_discovery.validate_extra_files()

        self.discovered_file_paths = extra_files_discovery.discovered_file_paths
        self.missing_file_paths = extra_files_discovery.missing_file_paths

        # Step 3: Enable component
        self.ess_config.setdefault(self.component_root_key, {})["enabled"] = True

        # Step 4: Apply component transformations
        self.config_to_ess_transformer.transform_from_config(self.input.config, self.migration.transformations)

        # Step 5: Handle secrets for the component using the transformer's method
        # This will update the root ESS config directly and create Kubernetes Secrets
        self.config_to_ess_transformer.handle_secrets(
            secret_discovery,
            self.component_root_key,
            self.secrets,
        )

        # Step 6: Check for override configurations and warn user
        self._check_overrides(self.input.config)

        # Step 7: Add filtered additional configurations (not from transformation)
        self.config_to_ess_transformer.add_additional_config_to_component(self.component_root_key, self.input.config)
