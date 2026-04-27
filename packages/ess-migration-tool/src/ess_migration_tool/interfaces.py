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
        """Get the user-facing name of the strategy (e.g., 'Synapse', 'Matrix Authentication Service')."""
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
    def secret_name(self) -> str:
        """Get the secret/strategy name in kebab-case."""
        ...

    def discover_component_specific_secrets(
        self, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], dict[str, str]]:
        """
        Discover component-specific secrets from configuration.

        Args:
            config_data: Component configuration data

        Returns:
            Tuple of (discovered_secrets, failed_secrets) where:
            - discovered_secrets: Dictionary mapping ESS secret keys to DiscoveredSecret objects
            - failed_secrets: Dictionary mapping ESS secret keys to error messages for
              secrets that were discovered but could not be read
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
    def component_name(self) -> str:
        """Get the component name for user-facing messages."""
        ...

    @property
    def component_root_key(self) -> str:
        """Get the component root key for ESS config (e.g., 'synapse', 'matrixAuthenticationService')."""
        ...
