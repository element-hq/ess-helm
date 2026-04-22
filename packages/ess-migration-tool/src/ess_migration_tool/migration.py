# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration service.
"""

import base64
import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from .extra_files import ExtraFilesDiscovery
from .interfaces import ExtraFilesDiscoveryStrategy, MigrationStrategy, SecretDiscoveryStrategy
from .models import (
    ConfigMap,
    DiscoveredExtraFile,
    DiscoveredSecret,
    GlobalOptions,
    MigrationInput,
    Secret,
    TransformationSpec,
)
from .secrets import SecretDiscovery
from .utils import (
    get_nested_value,
    remove_nested_value,
    set_nested_value,
    to_kebab_case,
    yaml_dump_with_pipe_for_multiline,
)

logger = logging.getLogger("migration")


def additional_config_transformer(
    config_value_transformer: "ConfigValueTransformer",
    value: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Generic transformer for additional config generation.

    Args:
        config_value_transformer: ConfigValueTransformer calling the transformer
        value: The value to transform
        **kwargs: Context parameters. See below.

    kwargs uses:
    - extra_files_discovery: ExtraFilesDiscovery | None containing the extra files discovery service
    - component_root_key: str - Internal ESS config key (e.g., "synapse")
    - override_configs: set[str] - Set of configuration paths managed by ESS
    - component_name: str - User-facing strategy name (e.g., "Synapse")
    """
    source_config = value  # value is the source config (when src_key is None)

    # Get context from kwargs
    component_root_key = kwargs.get("component_root_key", "")
    override_configs = kwargs.get("override_configs", set())
    extra_files_discovery = kwargs.get("extra_files_discovery")

    filtered_config = copy.deepcopy(source_config)

    # Filter out values already processed by other transformations
    for source_path in config_value_transformer.tracked_values:
        remove_nested_value(filtered_config, source_path)

    # Note: This runs after filtering so we check the remaining config
    # Get all src_keys from transformations that have been processed
    # Store warnings for future engine logging
    if override_configs and component_root_key:
        for override_config in override_configs:
            if get_nested_value(filtered_config, override_config) is not None:
                warning = (
                    f"⚠️  '{override_config}' found in {component_root_key}.additional[\"00-imported.yaml\"].config"
                )
                config_value_transformer.override_warnings.append(warning)

    # Update file paths if extra files were discovered
    if extra_files_discovery:
        filtered_config = config_value_transformer.update_paths_in_config(filtered_config, extra_files_discovery)

    # Return in the expected additional config format
    # Also preserve any existing entries in additional (like listeners.yml from other transformers)
    if filtered_config:
        # Check if there are existing entries in the component's additional section
        component_config = config_value_transformer.ess_config.get(component_root_key, {})
        existing_additional = component_config.get("additional", {})

        result = {"00-imported.yaml": {"config": yaml_dump_with_pipe_for_multiline(filtered_config)}}

        # Merge with existing entries - existing entries take precedence
        # This preserves listeners.yml, etc. added by other transformers
        merged = {**result, **existing_additional}
        return merged
    return {}


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

    pretty_logger: logging.Logger = field(init=True)  # Pretty logger
    ess_config: dict[str, Any] = field(init=True)  # Target ESS configuration dictionary
    results: list[TransformationResult] = field(default_factory=list)  # List of transformation results
    tracked_values: list[str] = field(default_factory=list)  # Source paths that have been processed
    override_warnings: list[str] = field(default_factory=list)  # Warnings about ESS-managed overrides

    def transform_from_config(
        self,
        source_config: dict[str, Any],
        transformations: list[TransformationSpec],
        extra_files_discovery: ExtraFilesDiscovery | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Transform values from a source configuration using explicit source and target path mappings.

        Args:
            source_config: Source configuration dictionary
            transformations: List of TransformationSpec objects
            extra_files_discovery: ExtraFilesDiscovery instance for context
            **kwargs: Additional context to pass to transformer functions
        """
        for transformation in transformations:
            # Get the value from the source configuration
            if transformation.src_key is None:
                value = source_config
            else:
                value = get_nested_value(source_config, transformation.src_key)

            # Handle transformer if provided
            if transformation.transformer is not None:
                # If transformer is provided, always call it (even if value is None)
                # This allows transformers to handle missing values (e.g., by prompting for input)
                # Pass self (ConfigValueTransformer) as first arg, context via named kwargs
                transformed_value = transformation.transformer(
                    self,
                    value,
                    extra_files_discovery=extra_files_discovery,
                    **kwargs,
                )
            else:
                # No transformer provided, use the raw value
                transformed_value = value

            # Check if we should skip this transformation
            if transformed_value is None and transformation.required:
                # If the transformation is required but the value is missing, raise an error
                raise MigrationError(
                    f"Required configuration value '{transformation.src_key}' is missing from the source configuration"
                )
            elif transformed_value is None:
                # Even if transformation returns None, track the source key so it gets filtered out
                # Skip tracking if src_key is None (it represents the full config, not a specific path)
                if transformation.src_key is not None and transformation.src_key not in self.tracked_values:
                    self.tracked_values.append(transformation.src_key)
                continue

            # Track the source path if not already tracked (skip None as it's not a filterable path)
            if transformation.src_key is not None and transformation.src_key not in self.tracked_values:
                self.tracked_values.append(transformation.src_key)

            # Create TransformationResult using the current transformation spec
            result = TransformationResult(spec=transformation, value=transformed_value)
            self.results.append(result)

            # Set the transformed value in the ESS config
            set_nested_value(self.ess_config, transformation.target_key, transformed_value)

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
        filtered_config = copy.deepcopy(config)

        for source_path in self.tracked_values:
            remove_nested_value(filtered_config, source_path)

        return filtered_config

    def update_paths_in_config(
        self,
        source_config: dict[str, Any],
        extra_files_discovery: ExtraFilesDiscovery,
    ):
        # Get the base mount path for the component
        base_mount_path = f"/etc/{extra_files_discovery.strategy.component_root_key}/extra"
        updated_config = copy.deepcopy(source_config)
        for discovered_path in extra_files_discovery.discovered_file_paths:
            if discovered_path.skipped_reason:
                continue
            # If it is a directory, files will be mounted as child of the directory name
            # If it is a file, files will be mounted as child of the `extra` folder
            mounted_path = f"{base_mount_path}/{discovered_path.source_path.name}"
            original_value = get_nested_value(updated_config, discovered_path.config_key)
            set_nested_value(updated_config, discovered_path.config_key, mounted_path)
            logging.info(f"Updated config: {discovered_path.config_key} = {original_value} -> {mounted_path}")
        return updated_config

    def handle_secrets(
        self,
        secret_discovery: SecretDiscovery,
        secrets_list: list[Secret],
    ) -> None:
        """
        Handle secrets for component using SecretDiscovery.

        Args:
            secret_discovery: SecretDiscovery instance
            secrets_list: List to append created secrets to

        Returns:
            ESS configuration dictionary with credential schema
        """
        # Skip if secret_service is None or no secrets discovered
        if secret_discovery is None or not secret_discovery.discovered_secrets:
            return

        # Create a Kubernetes Secret containing all discovered secrets
        secret_name = f"imported-{secret_discovery.strategy.secret_name}"
        secret_data = {}

        for secret_key, discover_secret in secret_discovery.discovered_secrets.items():
            # Base64 encode the secret value for Kubernetes Secret
            encoded_value = base64.b64encode(discover_secret.value.encode("utf-8")).decode("utf-8")
            secret_data[secret_key] = encoded_value

        secret = Secret(name=secret_name, data=secret_data)
        secrets_list.append(secret)
        logging.info(
            f"Created Kubernetes Secret with {len(secret_discovery.discovered_secrets)}"
            f" secrets for {secret_discovery.strategy.secret_name}"
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
            self.tracked_values.append(discover_secret.config_key)

    def handle_extra_files_mounts(
        self,
        extra_files_discovery: ExtraFilesDiscovery,
        component_root_key: str,
        config_maps: list[ConfigMap],
    ):
        config = self.get_component_config(component_root_key)
        # Get the base mount path for the component
        base_mount_path = f"/etc/{component_root_key}/extra"

        configmap_name = f"imported-{to_kebab_case(component_root_key)}"
        extra_volume_mounts: list[dict[str, Any]] = []
        extra_volumes: list[dict[str, Any]] = []

        configmap_data = {}

        for discovered_extra_file in extra_files_discovery.discovered_extra_files.values():
            # Encode the file content
            configmap_data[discovered_extra_file.filename] = discovered_extra_file.content.decode("utf-8")

        configmap = ConfigMap(name=configmap_name, data=configmap_data)

        # Add skipped paths to tracked_values for override detection
        for discovered_path in extra_files_discovery.discovered_file_paths:
            if discovered_path.skipped_reason:
                self.tracked_values.append(discovered_path.config_key)

        for extra_file in extra_files_discovery.discovered_extra_files.values():
            for discovered_path in extra_file.discovered_source_paths:
                if discovered_path.skipped_reason:
                    continue

                # See update_paths_in_config() for the `additional` side of this behaviour
                # If it is a directory, files must be mounted as child of the directory name
                # If it is a file, files must be mounted as child of the `extra` folder
                if discovered_path.is_dir:
                    mounted_path = f"{base_mount_path}/{discovered_path.source_path.name}/{extra_file.filename}"
                else:
                    mounted_path = f"{base_mount_path}/{extra_file.filename}"
                extra_volume_mounts.append(
                    {"name": configmap_name, "mountPath": mounted_path, "subPath": extra_file.filename}
                )
        if extra_volume_mounts:
            extra_volumes.append(
                {
                    "name": configmap_name,
                    "configMap": {"name": configmap_name},
                }
            )
            config_maps.append(configmap)

        extra_volume_mounts.sort(key=lambda x: x["mountPath"])

        if extra_volumes:
            config["extraVolumes"] = extra_volumes
            config["extraVolumeMounts"] = extra_volume_mounts


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
    results: list[TransformationResult] = field(default_factory=list)  # List of transformation results
    global_options: GlobalOptions = field(default_factory=GlobalOptions)  # Global migration options

    def __post_init__(self):
        self.override_configs = self.migration.override_configs

    def migrate(self) -> None:
        """
        Perform migration using the injected strategy.

        Migration steps:
        1. Apply component transformations
        2. Add filtered additional configurations
        """
        # Step 1: Discover secrets
        secret_discovery = SecretDiscovery(
            strategy=self.secret_discovery_strategy,
            source_file=self.input.config_path,
            pretty_logger=self.pretty_logger,
            global_options=self.global_options,
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

        config_to_ess_transformer = ConfigValueTransformer(self.pretty_logger, self.ess_config)

        # Step 3: Handle secrets for the component using the transformer's method
        # This will update the root ESS config directly and create Kubernetes Secrets
        config_to_ess_transformer.handle_secrets(
            secret_discovery,
            self.secrets,
        )

        # Step 4: Handle extra files mounts for the component using the transformer's method
        # This will update the root ESS config directly and create Kubernetes ConfigMaps
        config_to_ess_transformer.handle_extra_files_mounts(
            extra_files_discovery,
            self.extra_files_strategy.component_root_key,
            self.configmaps,
        )

        # Step 5: Apply component transformations
        # Note: component_root_key and other context are passed through TransformationSpec lambdas
        config_to_ess_transformer.transform_from_config(
            self.input.config,
            self.migration.transformations,
            extra_files_discovery=extra_files_discovery,
        )

        # Step 6: Store results and override warnings
        self.results.extend(config_to_ess_transformer.results)
        self.override_warnings.extend(config_to_ess_transformer.override_warnings)
