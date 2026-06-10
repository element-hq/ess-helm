# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Conflict resolution utilities for migration.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from .interfaces import SecretDiscoveryStrategy
from .models import GlobalOptions, ValueSourceTracking
from .rich_output import print_prompt, print_separator
from .utils import prompt_choice, prompt_value, set_nested_value


@dataclass
class SecretSource:
    """Represents a source of a discovered secret value."""

    strategy: SecretDiscoveryStrategy  # Name of the strategy that discovered the secret
    secret_key: str  # ESS secret key (e.g., "synapse.signingKey")
    value: str  # The secret value
    source_path: str  # Original configuration path in source file
    takes_precedence: bool = False  # Whether this strategy takes precedence for duplicates


def prompt_for_conflict_resolution(
    summary_logger: logging.Logger,
    conflict_key: str,
    value_to_strategies: dict[str, list[str]],
    global_options: GlobalOptions,
    display_value_max_length: int = 50,
    enable_custom: bool = False,
) -> tuple[str | None, bool]:
    """
    Prompt user to resolve a conflict.

    Args:
        summary_logger: Logger for displaying prompts
        conflict_key: The key/path being resolved (for display)
        value_to_strategies: Mapping of value strings to list of strategy names
        display_value_max_length: Max length for value display before truncation

    Returns:
        Tuple of (selected_value, is_custom) where is_custom indicates user wants to enter custom value
    """
    options = []
    # Sort options by strategies names
    for value, _ in sorted(value_to_strategies.items(), key=lambda v: "".join(sorted(v[1]))):
        options.append(value)
    if enable_custom:
        options.append("Enter custom value")

    choice = prompt_choice(
        summary_logger, f"Select value for '{conflict_key}':", options, global_options=global_options
    )
    is_custom = choice == "Enter custom value"
    selected_value = choice if not is_custom else None
    return selected_value, is_custom


def resolve_value_conflicts(
    summary_logger: logging.Logger,
    value_source_tracking: ValueSourceTracking,
    ess_config: dict[str, Any],
    global_options: GlobalOptions,
) -> None:
    """Resolve conflicts where multiple strategies provide different values for same ESS path."""
    conflicts = value_source_tracking.get_conflicts()
    if not conflicts:
        return

    for ess_path, sources in sorted(conflicts.items()):
        first_value = sources[0].value
        all_same = all(str(v.value) == str(first_value) for v in sources)

        if all_same:
            logging.debug(f"Consistent values for {ess_path}: {first_value}")
            continue

        if global_options.quiet_mode:
            logging.info(f"Conflict detected for {ess_path}, using first value: {first_value}")
            continue

        # Group by value
        value_to_strategies: dict[str, list[str]] = {}
        for source in sources:
            value_str = str(source.value)
            value_to_strategies.setdefault(value_str, []).append(source.strategy_name)

        print_prompt(f"⚠️  CONFLICT for '{ess_path}'", style="default", logger=summary_logger)
        print_prompt("   Multiple configurations provide different values:", style="default", logger=summary_logger)
        for source in sources:
            print_prompt(
                f"   • {source.strategy_name} ({source.source_path}): {source.value}",
                style="default",
                logger=summary_logger,
            )

        selected_value, is_custom = prompt_for_conflict_resolution(
            summary_logger, ess_path, value_to_strategies, enable_custom=True, global_options=global_options
        )

        if is_custom:
            selected_value = prompt_value(summary_logger, "Enter custom value:", global_options)

        set_nested_value(ess_config, ess_path, selected_value)
        logging.info(f"Resolved {ess_path} = {selected_value}")


@dataclass
class DiscoveredSecretTracking:
    """Tracks all discovered secrets across strategies to prevent duplicate prompts and detect conflicts."""

    sources: dict[str, list[SecretSource]] = field(default_factory=dict)

    def add_source(
        self,
        secret_key: str,
        strategy: SecretDiscoveryStrategy,
        value: str,
        source_path: str,
        takes_precedence: bool = False,
    ) -> None:
        """Add a discovered secret source to tracking."""
        if secret_key not in self.sources:
            self.sources[secret_key] = []
        self.sources[secret_key].append(
            SecretSource(
                strategy=strategy,
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
                strategies = set(s.strategy.name for s in sources)
                if len(strategies) > 1:
                    conflicts[secret_key] = sources
        return conflicts

    def get_strategies_for_secret(self, secret_key: str) -> list[SecretDiscoveryStrategy]:
        """Get all strategy names that discovered a particular secret."""
        if not self.is_discovered(secret_key):
            return []
        return [s.strategy for s in self.sources[secret_key]]

    def get_secret_owner(self, secret_key: str) -> SecretDiscoveryStrategy | None:
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
        logger = logging.getLogger("migration")

        # If secret was not discovered, return None
        if not self.is_discovered(secret_key):
            return None

        # Get all sources (strategies that discovered this secret)
        sources = self.sources.get(secret_key, [])

        # Find the strategy with takes_precedence=True
        owning_strategy: SecretDiscoveryStrategy | None = None
        found_precedence = False
        for source in sources:
            if owning_strategy is None:
                owning_strategy = source.strategy

            if source.takes_precedence:
                found_precedence = True
                # This strategy wants to own this secret
                if owning_strategy is not None:
                    # More than one strategy wants to own it - this is a conflict
                    logger.error(
                        f"Multiple strategies claim precedence for secret {secret_key}: "
                        f"{owning_strategy} and {source.strategy.name}. "
                    )
                owning_strategy = source.strategy

        # If no strategy has takes_precedence,
        if len(sources) > 1 and not found_precedence and owning_strategy:
            # More than one strategy wants to own it - this is a conflict
            logger.error(
                f"Multiple strategies discovered secret {secret_key}, but no strategy claims precedence: "
                f"{owning_strategy.name} and {source.strategy.name}. "
            )
            # Find the last strategy that discovered the secret
            owning_strategy = sources[-1].strategy
        return owning_strategy

    def resolve_secret_conflicts(self, summary_logger: logging.Logger, global_options: GlobalOptions) -> None:
        """Resolve conflicts where multiple strategies discovered different values for the same secret."""
        conflicts = self.get_conflicts()
        if not conflicts:
            return

        logger = logging.getLogger("migration")

        print_prompt("", style="default", logger=summary_logger)
        print_separator(logger=summary_logger)
        print_prompt("🔐 RESOLVING SECRET CONFLICTS", style="default", logger=summary_logger)
        print_separator(logger=summary_logger)
        print_prompt(
            "Some secrets were discovered by multiple strategies with different values.",
            style="default",
            logger=summary_logger,
        )
        print_prompt("Please select which value to use for each:", style="default", logger=summary_logger)
        print_prompt("", style="default", logger=summary_logger)

        if global_options.quiet_mode:
            for secret_key, sources in sorted(conflicts.items()):
                logger.info("Conflict for %s: using first value (from %s)", secret_key, sources[0].strategy.name)
                self.sources[secret_key] = [sources[0]]
            return

        for secret_key, sources in sorted(conflicts.items()):
            # Group by value
            value_to_strategies: dict[str, list[str]] = {}
            for source in sources:
                value_to_strategies.setdefault(source.value, []).append(source.strategy.name)

            print_prompt(f"⚠️  Conflict for secret: {secret_key}", style="default", logger=summary_logger)
            print_prompt(
                "   Discovered by multiple strategies with different values:", style="default", logger=summary_logger
            )
            for value, strategies in sorted(value_to_strategies.items(), key=lambda v: "".join(sorted(v[1]))):
                display_value = value if len(value) <= 50 else f"{value[:47]}..."
                print_prompt(
                    f"   • {display_value} (from: {', '.join(strategies)})", style="default", logger=summary_logger
                )

            selected_value, _ = prompt_for_conflict_resolution(
                summary_logger, secret_key, value_to_strategies, global_options
            )

            self.sources[secret_key] = [s for s in sources if s.value == selected_value]

            print_prompt(f"   ✅ Resolved {secret_key} using {selected_value}", style="default", logger=summary_logger)
            print_prompt("", style="default", logger=summary_logger)

        print_separator(logger=summary_logger)
