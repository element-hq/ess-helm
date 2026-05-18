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
    DiscoveredSecretTracking,
    GlobalOptions,
    MigrationInput,
    Secret,
    TransformationSpec,
    ValueSourceTracking,
)
from .secrets import SecretDiscovery
from .utils import (
    find_matching_schema_key,
    get_nested_value,
    press_enter_to_continue,
    remove_nested_value,
    set_nested_value,
    sort_tracked_values_for_filtering,
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
    - override_configs: set[str] - Set of configuration paths managed by ESS (users should not override)
    - underride_configs: set[str] - Set of configuration paths with ESS defaults (users can override)
    - serialization_format: str - Format for additional config: "yaml" (default) or "json"
    - use_file_object_format: bool - If True (default), return {"filename": {"config": string}} format.
      If False, return {"filename": string} format (direct string without wrapper object).
      Element Web uses False since its Helm template expects the value to be a JSON/YAML string directly.
    - filename: str - Custom filename to use instead of the default "00-imported.{serialization_format}".
      If provided, the file extension from serialization_format will be appended if not already present.
    """
    import json

    source_config = value  # value is the source config (when src_key is None)

    # Get context from kwargs
    component_root_key = kwargs.get("component_root_key", "")
    override_configs = kwargs.get("override_configs", set())
    underride_configs = kwargs.get("underride_configs", set())
    extra_files_discovery = kwargs.get("extra_files_discovery")
    serialization_format = kwargs.get("serialization_format", "yaml")
    use_file_object_format = kwargs.get("use_file_object_format", True)

    # Determine file name from custom filename or default
    file_name = kwargs.get("filename") or f"00-imported.{serialization_format}"

    # Get tracked source paths from value_source_tracking
    tracked_source_paths = config_value_transformer.value_source_tracking.get_tracked_source_paths(
        config_value_transformer.strategy_name
    )

    filtered_config = copy.deepcopy(source_config)

    # Filter out values already processed by other transformations
    # Sort tracked values so list indices are removed in descending order to avoid shifting
    sorted_tracked = sort_tracked_values_for_filtering(tracked_source_paths)
    for source_path in sorted_tracked:
        remove_nested_value(filtered_config, source_path)

    # Note: This runs after filtering so we check the remaining config
    # Store warnings for future engine logging
    config_path_suffix = f'"{file_name}"].config' if use_file_object_format else f'"{file_name}"]'

    # Check for override configs (ESS-managed values that users should not override)
    if override_configs and component_root_key:
        for override_config in override_configs:
            if get_nested_value(filtered_config, override_config) is not None:
                warning = (
                    f"⚠️  '{override_config}' found in {component_root_key}.additional"
                    f"[{config_path_suffix}] - ESS manages this, your setting may be ignored"
                )
                config_value_transformer.override_warnings.append(warning)

    # Check for underride configs (ESS defaults that users can override)
    if underride_configs and component_root_key:
        for underride_config in underride_configs:
            if get_nested_value(filtered_config, underride_config) is not None:
                warning = (
                    f"ℹ️  '{underride_config}' found in {component_root_key}.additional"
                    f"[{config_path_suffix}] - ESS default, your value overrides it"
                )
                config_value_transformer.underride_warnings.append(warning)

    # Update file paths if extra files were discovered
    if extra_files_discovery:
        config_value_transformer.update_paths_in_config(filtered_config, extra_files_discovery)

    # Check if there are existing entries in the component's additional section
    component_config = config_value_transformer.ess_config.get(component_root_key, {})
    existing_additional = component_config.get("additional", {})

    # Return in the expected additional config format
    # Also preserve any existing entries in additional (like listeners.yml from other transformers)
    # If there's nothing to add, return existing entries without creating a new entry
    if not filtered_config:
        return existing_additional

    # Serialize the config
    if serialization_format == "json":
        config_str = json.dumps(filtered_config, indent=2)
    else:
        config_str = yaml_dump_with_pipe_for_multiline(filtered_config)

    # Build result based on format preference
    if use_file_object_format:
        # Wrapped format: {"filename": {"config": string}}
        # Used by Synapse and MAS
        result: dict[str, Any] = {file_name: {"config": config_str}}
    else:
        # Direct string format: {"filename": string}
        # Used by Element Web, which expects the value to be a JSON/YAML string directly
        result = {file_name: config_str}

    # Merge with existing entries - existing entries take precedence
    # This preserves listeners.yml, etc. added by other transformers
    return {**result, **existing_additional}


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
    value_source_tracking: ValueSourceTracking = field(init=True)  # Shared value source tracking instance
    results: list[TransformationResult] = field(default_factory=list)  # List of transformation results
    override_warnings: list[str] = field(default_factory=list)  # Warnings about ESS-managed overrides
    underride_warnings: list[str] = field(default_factory=list)  # Warnings about ESS default configurations
    strategy_name: str = ""  # Name of the strategy (for source tracking)

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
                # Even if transformation returns None, track it so it gets filtered out
                if transformation.src_key is not None:
                    self.register_value_source(
                        ess_path=transformation.target_key,
                        strategy_name=self.strategy_name,
                        value=None,
                        source_path=transformation.src_key,
                    )
                continue

            # Create TransformationResult using the current transformation spec
            result = TransformationResult(spec=transformation, value=transformed_value)
            self.results.append(result)

            # Set the transformed value in the ESS config
            set_nested_value(self.ess_config, transformation.target_key, transformed_value)

            # Auto-register value source for target_key if it has a src_key
            if transformation.src_key is not None:
                self.register_value_source(
                    ess_path=transformation.target_key,
                    strategy_name=self.strategy_name,
                    value=transformed_value,
                    source_path=transformation.src_key,
                )

    def register_value_source(self, ess_path: str, strategy_name: str, value: Any | None, source_path: str) -> None:
        """Register that a strategy provides a value for an ESS path."""
        self.value_source_tracking.add_source(ess_path, strategy_name, value, source_path)

    def get_component_config(self, component_key: str) -> dict[str, Any]:
        """
        Get the configuration for a specific component.
        Uses setdefault to ensure the component config exists in ess_config.

        Args:
            component_key: The component key (e.g., "synapse", "matrixAuthenticationService")

        Returns:
            Dictionary with the component configuration, or empty dict if not found
        """
        return self.ess_config.setdefault(component_key, {})

    def update_paths_in_config(
        self,
        source_config: dict[str, Any],
        extra_files_discovery: ExtraFilesDiscovery,
    ):
        # Get the base mount path for the component
        base_mount_path = f"/etc/{extra_files_discovery.strategy.component_root_key}/extra"
        for discovered_path in extra_files_discovery.discovered_file_paths:
            if discovered_path.skipped_reason:
                continue
            # If it is a directory, files will be mounted as child of the directory name
            # If it is a file, files will be mounted as child of the `extra` folder
            mounted_path = f"{base_mount_path}/{discovered_path.source_path.name}"
            original_value = get_nested_value(source_config, discovered_path.config_key)
            set_nested_value(source_config, discovered_path.config_key, mounted_path)
            logging.info(f"Updated config: {discovered_path.config_key} = {original_value} -> {mounted_path}")

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
        if not secret_discovery.discovered_secrets:
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

            # Validate that the secret key matches a schema entry (supports wildcard patterns)
            matching_key = find_matching_schema_key(secret_key, secret_discovery.strategy.ess_secret_schema)
            if matching_key is None:
                raise RuntimeError(f"No ESS configuration mapping found for secret key: {secret_key}")

            # Set the credential config in the ESS config under the component section
            set_nested_value(self.ess_config, discover_secret.secret_key, credential_config)

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

        # Maximum file size to load into ConfigMap (1MB)
        # Larger files are skipped to prevent memory issues
        MAX_EXTRA_FILE_SIZE = 1 * 1024 * 1024

        for discovered_extra_file in extra_files_discovery.discovered_extra_files.values():
            # Skip non-cleartext files (binary files)
            if not discovered_extra_file.cleartext:
                logger.debug(f"Skipping non-cleartext file: {discovered_extra_file.filename}")
                continue

            # Skip files that are too large
            if (
                discovered_extra_file.source_path is not None
                and discovered_extra_file.source_path.stat().st_size > MAX_EXTRA_FILE_SIZE
            ):
                logger.warning(
                    f"Skipping large file {discovered_extra_file.source_path} "
                    f"({discovered_extra_file.source_path.stat().st_size} bytes > {MAX_EXTRA_FILE_SIZE} bytes)"
                )
                press_enter_to_continue(pretty_logger=self.pretty_logger)
                continue

            # Read content from source_path (lazy loading - content read once here, not during discovery)
            if discovered_extra_file.source_path is not None:
                try:
                    with open(discovered_extra_file.source_path, encoding="utf-8") as f:
                        content = f.read()
                    configmap_data[discovered_extra_file.filename] = content
                except Exception as e:
                    logger.warning(f"Failed to read file {discovered_extra_file.source_path}: {e}")
                    continue
            else:
                logger.warning(f"No source_path for discovered extra file: {discovered_extra_file.filename}")
                continue

        configmap = ConfigMap(name=configmap_name, data=configmap_data)

        # Add skipped paths to tracking for filtering
        for discovered_path in extra_files_discovery.discovered_file_paths:
            if discovered_path.skipped_reason:
                self.register_value_source(
                    ess_path=discovered_path.config_key,
                    strategy_name=self.strategy_name,
                    value=None,
                    source_path=discovered_path.config_key,
                )

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
    secret_discovery_strategy: SecretDiscoveryStrategy | None = field(init=True)  # Secret discovery service
    value_source_tracking: ValueSourceTracking = field(init=True)  # Shared value source tracking instance
    secret_tracking: DiscoveredSecretTracking = field(
        default_factory=DiscoveredSecretTracking
    )  # Global tracking of discovered secrets
    override_warnings: list[str] = field(default_factory=list)  # Warnings about overridden configurations
    underride_warnings: list[str] = field(default_factory=list)  # Warnings about ESS default configurations
    discovered_extra_files: list[DiscoveredExtraFile] = field(default_factory=list)  # List of discovered secrets
    secrets: list[Secret] = field(default_factory=list)  # List of created Secrets
    configmaps: list[ConfigMap] = field(default_factory=list)  # List of created ConfigMaps
    override_configs: set[str] = field(default_factory=set)  # Set of configurations that are managed by ESS
    underride_configs: set[str] = field(default_factory=set)  # Set of configurations that are ESS defaults
    results: list[TransformationResult] = field(default_factory=list)  # List of transformation results
    global_options: GlobalOptions = field(default_factory=GlobalOptions)  # Global migration options
    secret_discovery: SecretDiscovery | None = field(default=None)  # Secret discovery instance for this migrator

    def __post_init__(self):
        self.override_configs = self.migration.override_configs
        self.underride_configs = self.migration.underride_configs

    def migrate(self) -> None:
        """
        Perform migration using the injected strategy.

        Migration steps:
        1. Apply component transformations
        2. Add filtered additional configurations
        """
        # Step 1: Discover secrets
        if self.secret_discovery_strategy:
            self.secret_discovery = SecretDiscovery(
                strategy=self.secret_discovery_strategy,
                source_file=self.input.config_path,
                pretty_logger=self.pretty_logger,
                global_options=self.global_options,
                secret_tracking=self.secret_tracking,
            )
            self.secret_discovery.discover_secrets(self.input.config)
            # Note: prompt_for_missing_secrets() and validate_required_secrets()
            # are called in MigrationEngine after all strategies have run
        else:
            self.secret_discovery = None

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

        config_to_ess_transformer = ConfigValueTransformer(
            self.pretty_logger, self.ess_config, self.value_source_tracking
        )

        # Set strategy name for source tracking
        config_to_ess_transformer.strategy_name = self.migration.name

        # Register secret sources for filtering before transformations run
        self.register_secret_sources(config_to_ess_transformer)

        # Step 3: Handle extra files mounts for the component using the transformer's method
        # This will update the root ESS config directly and create Kubernetes ConfigMaps
        config_to_ess_transformer.handle_extra_files_mounts(
            extra_files_discovery,
            self.extra_files_strategy.component_root_key,
            self.configmaps,
        )

        # Step 4: Apply component transformations
        # Note: component_root_key and other context are passed through TransformationSpec lambdas
        config_to_ess_transformer.transform_from_config(
            self.input.config,
            self.migration.transformations,
            extra_files_discovery=extra_files_discovery,
        )

        # Step 6: Store results and override/underride warnings
        self.results.extend(config_to_ess_transformer.results)
        self.override_warnings.extend(config_to_ess_transformer.override_warnings)
        self.underride_warnings.extend(config_to_ess_transformer.underride_warnings)

    def register_secret_sources(self, transformer: ConfigValueTransformer) -> None:
        """
        Register value sources for all discovered secrets for filtering purposes.
        This must be called before transform_from_config() to ensure secrets are
        filtered out from the additional configuration.

        Args:
            transformer: The ConfigValueTransformer whose tracking should receive the secret sources
        """
        if self.secret_discovery is None:
            return

        for secret_key, discover_secret in self.secret_discovery.discovered_secrets.items():
            transformer.value_source_tracking.add_source(
                ess_path=secret_key,
                strategy_name=self.migration.name,
                value=None,
                source_path=discover_secret.config_key,
            )

    def handle_secrets_phase(self) -> None:
        """
        Handle secrets phase - creates Kubernetes Secrets for all discovered secrets.
        Called after prompt_for_missing_secrets() to ensure all secrets (including
        prompted ones) are processed.
        """
        if self.secret_discovery is None:
            return

        config_to_ess_transformer = ConfigValueTransformer(
            self.pretty_logger, self.ess_config, self.value_source_tracking
        )
        config_to_ess_transformer.strategy_name = self.migration.name

        config_to_ess_transformer.handle_secrets(
            self.secret_discovery,
            self.secrets,
        )
