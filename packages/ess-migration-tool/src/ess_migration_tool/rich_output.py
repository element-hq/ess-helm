# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Rich output utilities for the migration tool.
Provides styled console output using the Rich library for tables.
"""

import logging
import os
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Global console instance
_console: Console | None = None


def get_console() -> Console:
    """Get or create the global Rich Console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def is_rich_enabled() -> bool:
    """
    Check if Rich output should be used.
    Returns False if running under pytest or output is not a TTY.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return get_console().is_terminal


def print_table(
    data: list[list[str | Any]],
    headers: list[str],
    title: str = "",
    logger: logging.Logger | None = None,
) -> None:
    """
    Print data in a formatted table using Rich if available, otherwise use plain text.

    Args:
        data: List of rows, where each row is a list of cell values
        headers: List of column headers
        title: Optional table title
        logger: Logger to use for fallback output
    """
    if not is_rich_enabled():
        # Fallback to plain text using the provided logger
        if logger is not None:
            if title:
                logger.info(f"\n{title}")
                logger.info("-" * len(title))
            # Print headers
            logger.info("  ".join(headers))
            # Print separator
            logger.info("-" * (sum(len(h) for h in headers) + 2 * (len(headers) - 1)))
            # Print rows
            for row in data:
                logger.info("  ".join(str(cell) for cell in row))
        return

    # Rich is enabled - use styled table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    for header in headers:
        table.add_column(header)

    for row in data:
        table.add_row(*[str(cell) for cell in row])

    if title:
        panel = Panel(table, title=title, border_style="cyan", style="bold")
        get_console().print(panel)
    else:
        get_console().print(table)
