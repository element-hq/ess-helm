# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Data models for the migration script using Python dataclasses.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Secret:
    """Represents a Kubernetes Secret resource."""

    name: str  # Name of the Kubernetes Secret
    data: dict[str, str]  # Dictionary of secret key-value pairs (values should be base64 encoded)
    namespace: str | None = None  # Optional namespace for the Secret (None for default namespace)

    def to_manifest(self) -> dict[str, Any]:
        """Convert to Kubernetes manifest format."""
        metadata = {"name": self.name}
        if self.namespace:
            metadata["namespace"] = self.namespace
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": metadata,
            "data": self.data,
        }


@dataclass
class MigrationInput:
    """Represents all input data for the migration process."""

    name: str = field(default="")  # Name of the configuration
    config_path: str = field(default="")  # Path to the configuration file
    config: dict[str, Any] = field(default_factory=dict)  # Source configuration data


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    pass


@dataclass
class DiscoveredSecret:
    """Represents a discovered secret with source and target information."""

    source_file: str  # Source configuration file (e.g., "synapse.yaml", "mas.yaml")
    secret_key: str  # ESS secret key (e.g., "synapse.postgres.password")
    value: str  # Secret value
    config_key: str  # Original configuration path in source file


@dataclass
class DiscoveredPath:
    """Represents an extra file with source and target information."""

    config_key: str  # Original configuration path in source file
    source_file: str = field(init=True)  # Source configuration file (e.g., "synapse.yaml", "mas.yaml")
    source_path: Path = field(init=True)  # Original file path in source file
    is_dir: bool = field(default=False)  # If true, the original file path is a directory
    skipped_reason: str | None = field(default=None)  # Reason for skipping the file


@dataclass
class DiscoveredExtraFile:
    """Represents an extra file with source and target information."""

    discovered_source_paths: list[DiscoveredPath] = field(
        init=True
    )  # Source configuration file (e.g., "synapse.yaml", "mas.yaml")
    filename: str = field(init=True)  # Original file path in source file
    # and the file was discovered by listing its content
    content: bytes = field(default_factory=bytes)  # Extra file content. File bigger than 100KiB will be skipped
    cleartext: bool = field(default=True)  # If true, the file will be stored in a ConfigMap


@dataclass
class ConfigMap:
    """Represents a Kubernetes ConfigMap resource."""

    name: str  # Name of the Kubernetes ConfigMap
    data: dict[str, str]  # Dictionary of configuration key-value pairs
    namespace: str | None = None  # Optional namespace for the ConfigMap (None for default namespace)

    def to_manifest(self) -> dict[str, Any]:
        """Convert to Kubernetes manifest format."""
        metadata = {"name": self.name}
        if self.namespace:
            metadata["namespace"] = self.namespace
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": metadata,
            "data": self.data,
        }


@dataclass
class SecretConfig:
    init_if_missing_from_source_cfg: bool  # Whether to initialize secret if missing from source config
    description: str  # User-friendly description of the secret
    config_inline: str | None  # Configuration path for inline secret values
    config_path: str | None  # Configuration path for secret file paths
    transformer: Callable[[str], str | None] | None = (
        None  # Optional transformer function for extracting secrets from complex values
    )
