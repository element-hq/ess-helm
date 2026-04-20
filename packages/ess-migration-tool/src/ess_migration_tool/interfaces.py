# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Interfaces for the migration system.
"""

from typing import Protocol, runtime_checkable

from .models import DiscoveredSecret, GlobalOptions, SecretConfig, TransformationSpec


@runtime_checkable
class MigrationStrategy(Protocol):
    """Interface for migration strategies."""

    def __init__(self, global_options: GlobalOptions):
        """Initialize with global options."""
        ...

    @property
    def name(self) -> str:
        """Get the strategy name (e.g., 'synapse', 'matrixAuthenticationService')."""
        ...

    @property
    def override_configs(self) -> set[str]:
        """Get component-specific override configurations."""
        ...

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get component-specific transformations based on global options."""
        ...


@runtime_checkable
class SecretDiscoveryStrategy(Protocol):
    """Minimal interface for secret discovery strategies."""

    def __init__(self, global_options: GlobalOptions):
        """Initialize with global options."""
        ...

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Get the ESS secret schema for this component."""
        ...

    @property
    def name(self) -> str:
        """Get the strategy name for user-facing messages."""
        ...

    def discover_component_specific_secrets(self, config_data: dict) -> dict[str, DiscoveredSecret]:
        """
        Discover component-specific secrets from configuration.

        Args:
            config_data: Component configuration data

        Returns:
            Dictionary mapping ESS secret keys to DiscoveredSecret objects
        """
        ...


@runtime_checkable
class ExtraFilesDiscoveryStrategy(Protocol):
    """Minimal interface for extra file discovery strategies."""

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        ...

    @property
    def ignored_config_keys(self) -> list[str]:
        """Config keys to ignore when discovering extra files."""
        ...

    @property
    def name(self) -> str:
        """Get the strategy name for user-facing messages."""
        ...
