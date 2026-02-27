# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Interfaces for the migration system.
"""

from typing import Any, Protocol, runtime_checkable

from .models import SecretConfig


@runtime_checkable
class MigrationStrategy(Protocol):
    """Interface for migration strategies."""

    @property
    def component_root_key(self) -> str:
        """Get the component root key (e.g., 'synapse', 'matrixAuthenticationService')."""
        ...

    @property
    def override_configs(self) -> set[str]:
        """Get component-specific override configurations."""
        ...

    @property
    def transformations(self) -> list[Any]:
        """Get component-specific transformations."""
        ...


@runtime_checkable
class SecretDiscoveryStrategy(Protocol):
    """Minimal interface for secret discovery strategies."""

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Get the ESS secret schema for this component."""
        ...

    @property
    def component_name(self) -> str:
        """Get the component name for user-facing messages."""
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
