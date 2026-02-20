# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Data models for the migration script using Python dataclasses.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MigrationInput:
    """Represents all input data for the migration process."""

    name: str = field(default="")  # Name of the configuration
    config_path: str = field(default="")  # Path to the configuration file
    config: dict[str, Any] = field(default_factory=dict)  # Source configuration data


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    pass
