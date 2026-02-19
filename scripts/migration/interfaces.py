# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Interfaces for the migration system.
"""

from typing import Any, Protocol, runtime_checkable


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
