# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Conflict resolution utilities for migration.
"""

import logging
from typing import Any

from .models import DiscoveredSecretTracking, GlobalOptions, SecretSource, ValueSourceTracking
from .rich_output import print_prompt, print_separator
from .utils import prompt_choice, prompt_value, set_nested_value


def prompt_for_conflict_resolution(
    summary_logger: logging.Logger,
    conflict_key: str,
    value_to_strategies: dict[str, list[str]],
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
    for value in sorted(value_to_strategies):
        options.append(value)
    if enable_custom:
        options.append("Enter custom value")

    choice = prompt_choice(summary_logger, f"Select value for '{conflict_key}':", options)
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
            summary_logger, ess_path, value_to_strategies, enable_custom=True
        )

        if is_custom:
            selected_value = prompt_value(summary_logger, "Enter custom value:")

        set_nested_value(ess_config, ess_path, selected_value)
        logging.info(f"Resolved {ess_path} = {selected_value}")


def resolve_secret_conflicts(
    summary_logger: logging.Logger, secret_tracking: DiscoveredSecretTracking, global_options: GlobalOptions
) -> None:
    """Resolve conflicts where multiple strategies discovered different values for the same secret."""
    conflicts = secret_tracking.get_conflicts()
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
            logger.info("Conflict for %s: using first value (from %s)", secret_key, sources[0].strategy_name)
            secret_tracking.sources[secret_key] = [sources[0]]
        return

    for secret_key, sources in sorted(conflicts.items()):
        # Group by value
        value_to_strategies: dict[str, list[str]] = {}
        for source in sources:
            value_to_strategies.setdefault(source.value, []).append(source.strategy_name)

        print_prompt(f"⚠️  Conflict for secret: {secret_key}", style="default", logger=summary_logger)
        print_prompt(
            "   Discovered by multiple strategies with different values:", style="default", logger=summary_logger
        )
        for value, strategies in sorted(value_to_strategies.items()):
            display_value = value if len(value) <= 50 else f"{value[:47]}..."
            print_prompt(
                f"   • {display_value} (from: {', '.join(strategies)})", style="default", logger=summary_logger
            )

        selected_value, is_custom = prompt_for_conflict_resolution(summary_logger, secret_key, value_to_strategies)

        if is_custom:
            new_value = prompt_value(summary_logger, "Enter custom value:")
            secret_tracking.sources[secret_key] = [
                SecretSource(
                    strategy_name="user-provided",
                    secret_key=secret_key,
                    value=new_value,
                    source_path="user input",
                )
            ]
        else:
            secret_tracking.sources[secret_key] = [s for s in sources if s.value == selected_value]

        print_prompt(f"   ✅ Resolved {secret_key}", style="default", logger=summary_logger)
        print_prompt("", style="default", logger=summary_logger)

    print_separator(logger=summary_logger)
