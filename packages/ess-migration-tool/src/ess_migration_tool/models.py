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
class GlobalOptions:
    """
    Global migration options that affect transformation behavior.
    """

    use_existing_database: bool | None = None
    quiet_mode: bool | None = None


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
class TransformationSpec:
    """
    Specification for a configuration transformation.

    Defines how to map from a source configuration path to a target ESS path.
    When src_key is None, the full config is passed to the transformer.
    """

    src_key: str | None  # Source configuration path (None means full config)
    target_key: str  # Target ESS configuration path
    required: bool = True  # Whether this transformation is required
    transformer: Callable[..., Any] | None = None  # Optional transformation function


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
    source_path: Path | None = field(default=None)  # Path to the source file (lazy-loaded, not content)
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
    """Configuration for discovering secrets from config files (inline or file path)."""

    config_inline: str | None  # Configuration path for inline secret values
    config_path: str | None  # Configuration path for secret file paths
    transformer: Callable[[str], str | None] | None = (
        None  # Optional transformer function for extracting secrets from complex values
    )


@dataclass
class DiscoverableSecret:
    """A discoverable secret with metadata and discovery configuration."""

    description: str  # User-friendly description of the secret
    discovery: SecretConfig | None = None  # Discovery configuration (None if not discoverable from config)
    optional: bool = False  # Whether the secret is optional (not required for migration)
    init_if_missing_from_source_cfg: bool = False  # Whether to initialize secret if missing from source config
    takes_precedence_if_duplicates: bool = (
        False  # If True, this strategy owns the secret when discovered by multiple strategies
    )


@dataclass
class ValueSource:
    """Represents a source of a value for an ESS configuration path."""

    strategy_name: str
    source_path: str
    value: Any | None


@dataclass
class ValueSourceTracking:
    """Tracks all sources for ESS configuration values across strategies."""

    sources: dict[str, list[ValueSource]] = field(default_factory=dict)

    def add_source(self, ess_path: str, strategy_name: str, value: Any | None, source_path: str) -> None:
        """Add a source for an ESS path."""
        if ess_path not in self.sources:
            self.sources[ess_path] = []
        self.sources[ess_path].append(ValueSource(strategy_name=strategy_name, source_path=source_path, value=value))

    def get_conflicts(self) -> dict[str, list[ValueSource]]:
        """Get all ESS paths that have multiple sources from different strategies."""
        conflicts = {}
        for path, srcs in self.sources.items():
            # Filter out sources with None values
            srcs_with_values = [s for s in srcs if s.value is not None]
            if len(srcs_with_values) > 1:
                strategies = set(s.strategy_name for s in srcs_with_values)
                if len(strategies) > 1:
                    conflicts[path] = srcs_with_values
        return conflicts

    def get_tracked_source_paths(self, strategy_name: str) -> list[str]:
        """Get all source paths that have been tracked (for filtering in additional config)."""
        return [
            s.source_path
            for srcs in self.sources.values()
            for s in srcs
            if s.source_path is not None and s.strategy_name == strategy_name
        ]


@dataclass
class SecretSource:
    """Represents a source of a discovered secret value."""

    strategy_name: str  # Name of the strategy that discovered the secret
    secret_key: str  # ESS secret key (e.g., "synapse.signingKey")
    value: str  # The secret value
    source_path: str  # Original configuration path in source file
    takes_precedence: bool = False  # Whether this strategy takes precedence for duplicates


@dataclass
class DiscoveredSecretTracking:
    """Tracks all discovered secrets across strategies to prevent duplicate prompts and detect conflicts."""

    sources: dict[str, list[SecretSource]] = field(default_factory=dict)

    def add_source(
        self, secret_key: str, strategy_name: str, value: str, source_path: str, takes_precedence: bool = False
    ) -> None:
        """Add a discovered secret source to tracking."""
        if secret_key not in self.sources:
            self.sources[secret_key] = []
        self.sources[secret_key].append(
            SecretSource(
                strategy_name=strategy_name,
                secret_key=secret_key,
                value=value,
                source_path=source_path,
                takes_precedence=takes_precedence,
            )
        )

    def is_discovered(self, secret_key: str) -> bool:
        """Check if a secret has been discovered by any strategy."""
        return secret_key in self.sources and len(self.sources[secret_key]) > 0

    def get_all_values(self, secret_key: str) -> list[str]:
        """Get all discovered values for a secret key."""
        if not self.is_discovered(secret_key):
            return []
        return [s.value for s in self.sources[secret_key]]

    def get_conflicts(self) -> dict[str, list[SecretSource]]:
        """Get all secret keys that have multiple sources with different values from different strategies."""
        conflicts = {}
        for secret_key, sources in self.sources.items():
            # Get unique values
            unique_values = set(s.value for s in sources)
            if len(unique_values) > 1:
                # Check if different strategies discovered different values
                strategies = set(s.strategy_name for s in sources)
                if len(strategies) > 1:
                    conflicts[secret_key] = sources
        return conflicts

    def get_strategies_for_secret(self, secret_key: str) -> list[str]:
        """Get all strategy names that discovered a particular secret."""
        if not self.is_discovered(secret_key):
            return []
        return [s.strategy_name for s in self.sources[secret_key]]

    def get_secret_owner(self, secret_key: str) -> str | None:
        """
        Determine which strategy owns a secret that was discovered by multiple strategies.
        A strategy owns a secret if it has `takes_precedence_if_duplicates=True` for that secret.
        Only one strategy can own a duplicate secret.
        If no strategy claims precedence or multiple claim it, falls back to the last
        discovering strategy.

        Args:
            secret_key: The ESS secret key to determine ownership for

        Returns:
            The strategy name that owns this secret, or None if secret was not discovered
        """
        import logging

        logger = logging.getLogger("migration")

        # If secret was not discovered, return None
        if not self.is_discovered(secret_key):
            return None

        # Get all sources (strategies that discovered this secret)
        sources = self.sources.get(secret_key, [])

        # Find the strategy with takes_precedence=True
        owning_strategy: str | None = None
        found_precedence = False
        for source in sources:
            if source.takes_precedence:
                found_precedence = True
                # This strategy wants to own this secret
                if owning_strategy is not None:
                    # More than one strategy wants to own it - this is a conflict
                    logger.error(
                        f"Multiple strategies claim precedence for secret {secret_key}: "
                        f"{owning_strategy} and {source.strategy_name}. "
                    )
                owning_strategy = source.strategy_name

        # If no strategy has takes_precedence,
        if len(sources) > 1 and not found_precedence:
            # More than one strategy wants to own it - this is a conflict
            logger.error(
                f"Multiple strategies discovered secret {secret_key}, but no strategy claims precedence: "
                f"{owning_strategy} and {source.strategy_name}. "
            )
            # Find the last strategy that discovered the secret
            owning_strategy = sources[-1].strategy_name
        return owning_strategy
