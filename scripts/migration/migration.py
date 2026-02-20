# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration service.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .interfaces import MigrationStrategy
from .models import MigrationInput
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
                    transformed_value = transformation.transformer(value)

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


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    pass


@dataclass
class MigrationService:
    """Migration service."""

    input: MigrationInput = field(init=True)  # Migration input data
    ess_config: dict[str, Any] = field(init=True)  # Target ESS configuration
    migration: MigrationStrategy = field(init=True)  # Migration strategy
    override_warnings: list[str] = field(default_factory=list)  # Warnings about overridden configurations
    override_configs: set[str] = field(default_factory=set)  # Set of configurations that are managed by ESS
    component_root_key: str = field(init=False)  # Root key for the component (e.g., 'synapse')
    config_to_ess_transformer: ConfigValueTransformer = field(default_factory=ConfigValueTransformer)  # Config

    def __post_init__(self):
        self.component_root_key = self.migration.component_root_key
        self.override_configs = self.migration.override_configs
        self.config_to_ess_transformer.ess_config = self.ess_config

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

    def migrate(self) -> None:
        """
        Perform migration using the injected strategy.

        Migration steps:
        1. Enable component
        1. Apply component transformations
        2. Check for override configurations
        3. Add filtered additional configurations
        """
        # Step 1: Enable component
        self.ess_config.setdefault(self.component_root_key, {})["enabled"] = True

        # Step 2: Apply component transformations
        self.config_to_ess_transformer.transform_from_config(self.input.config, self.migration.transformations)

        # Step 3: Check for override configurations and warn user
        self._check_overrides(self.input.config)

        # Step 4: Add filtered additional configurations (not from transformation)
        self.config_to_ess_transformer.add_additional_config_to_component(self.component_root_key, self.input.config)
