# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Rich output utilities for the migration tool.
Provides styled console output using the Rich library for tables.
"""

import logging
import os
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

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
    logger: logging.Logger,
    title: str = "",
) -> None:
    """
    Print data in a formatted table using Rich if available, otherwise use plain text.

    Args:
        data: List of rows, where each row is a list of cell values
        headers: List of column headers
        title: Optional table title
        logger: Logger to use for fallback output
    """
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


def print_section(
    text: str,
    logger: logging.Logger,
    style: str = "bold cyan",
    border_style: str = "cyan",
    separator: str = "=",
) -> None:
    """
    Print a styled section header using Rich if available, otherwise use plain text.

    Args:
        text: The section header text to display
        style: Rich style string for the text (default: "bold cyan")
        border_style: Rich style string for the border/panel (default: "cyan")
        logger: Logger to use for fallback output
        separator: Character to use for separator line in plain text mode (default: "=")
    """
    # Log to file
    logger.info(f"\n{text}")
    logger.info(separator * len(text))

    # Rich is enabled - use styled panel for section header
    panel = Panel(
        Text(text, style=style),
        border_style=border_style,
        box=box.ROUNDED,
        padding=(0, 2),
    )
    get_console().print(panel)


def print_header(
    text: str,
    logger: logging.Logger,
    style: str = "bold green",
) -> None:
    """
    Print a styled header using Rich if available, otherwise use plain text.
    This is distinct from section headers - uses green color without a panel.

    Args:
        text: The header text to display
        style: Rich style string for the text (default: "bold green")
        logger: Logger to use for fallback output
    """
    # Log to file
    logger.info(f"\n{text}")

    # Rich is enabled - use styled text without panel
    get_console().print(Text(text, style=style))


def log_command(
    command: str,
    logger: logging.Logger,
) -> None:
    """
    Display a command with syntax highlighting using Rich.

    Args:
        command: The command string to display
        logger: Logger for fallback output when Rich is disabled
    """
    logger.info(f"   {command}")

    # Rich is enabled - use syntax highlighting
    syntax = Syntax(command, "bash", theme="monokai", word_wrap=True)
    get_console().print(syntax)


def print_prompt(
    message: str,
    logger: logging.Logger,
    style: str = "bold",
    prefix: str = "   ",
) -> None:
    """
    Print a prompt message with Rich styling if available.

    Args:
        message: The prompt message to display
        style: Rich style string for the text (default: "bold")
        logger: Logger to use for fallback output when Rich is disabled
        prefix: Prefix string to add before the message (default: "   ")
    """
    logger.info(f"{prefix}{message}")

    # Rich is enabled - use styled text
    styled = Text(f"{prefix}{message}", style=style)
    get_console().print(styled)


def print_separator(
    logger: logging.Logger,
) -> None:
    """
    Print a separator line using Rich styling if available.
    Uses terminal width when Rich is enabled, falls back to 60 for plain text.

    Args:
        logger: Logger to use for fallback output when Rich is disabled
    """
    logger.info("=" * 60)

    # Rich is enabled - use a styled separator with terminal width
    console = get_console()
    separator = "─" * console.width
    console.print(separator, style="cyan")


def print_output_tree(
    output_dir: str,
    file_paths: list[str],
    logger: logging.Logger,
) -> None:
    """
    Print the output directory file tree using Rich styling if available.

    Args:
        output_dir: Path to the output directory
        file_paths: List of file paths to display
        logger: Logger to use for fallback output when Rich is disabled
    """
    logger.info(f"📁 Output files written to: {output_dir}")

    console = get_console()
    output_path = Path(output_dir)

    tree = Tree(
        Text(f"📁 {output_path.name}", style="bold white"),
        guide_style="cyan",
    )

    for file_path in sorted(file_paths):
        path_obj = Path(file_path)
        try:
            relative = path_obj.relative_to(output_path)
        except ValueError:
            relative = path_obj
        tree.add(Text(str(relative), style="green"))

    console.print(tree)


class ProgressReporter:
    """
    Handles progress reporting for the migration process.
    Uses Rich for styled output when available.
    """

    def __init__(
        self,
        summary_logger: logging.Logger,
        steps: list[str],
        *,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the progress reporter.

        Args:
            summary_logger: Logger for output
            steps: List of step names in order
            verbose: Enable verbose logging
        """
        self.summary_logger = summary_logger
        self.verbose = verbose
        self.current_step: int = -1
        self.all_steps = steps

    def start_migration(self) -> None:
        """Report migration start."""
        print_header("🚀 Starting ESS Migration", logger=self.summary_logger)

    def report_step(self, step_name: str) -> None:
        """Report progress on a specific step."""
        if step_name != self.all_steps[self.current_step + 1]:
            raise ValueError("Migration engine tried to run an unexpected step")

        self.current_step += 1
        progress = (self.current_step + 1) / len(self.all_steps) * 100

        # Build a styled progress bar using block characters
        bar_width = 10
        completed = int(progress / 100 * bar_width)
        bar = "[" + "▰" * completed + "▱" * (bar_width - completed) + "]"

        if is_rich_enabled():
            # Rich is enabled - use styled output
            step_msg_rich = Text.assemble(
                (f"📦 Step {self.current_step + 1}/{len(self.all_steps)} ", "bold"),
                (f"{progress:.0f}% ", "green"),
                (bar + " ", "green"),
                (step_name, "bold white"),
            )
            get_console().print(step_msg_rich)
        else:
            # Fallback to plain text for non-Rich environments
            step_msg_plain = f"📦 Step {self.current_step + 1}/{len(self.all_steps)} ({progress:.0f}%): {step_name}"
            print_prompt(step_msg_plain, style="default", logger=self.summary_logger)

        # Pause for user input after each step (unless in quiet mode or testing)
        if not os.environ.get("PYTEST_CURRENT_TEST") and self.summary_logger.level != logging.CRITICAL:
            print_prompt("   Press Enter to continue...", style="default", logger=self.summary_logger)
            get_console().input()

    def report_success(self, output_dir: str, file_paths: list[str]) -> None:
        """Report successful completion.

        Args:
            output_dir: Path to the output directory
            file_paths: Optional list of file paths that were written
        """
        print_prompt("✅ Migration completed successfully!", logger=self.summary_logger, style="bold green")
        print_output_tree(output_dir, file_paths, logger=self.summary_logger)
        print_prompt("🎉 Ready to deploy with Element Server Suite!", logger=self.summary_logger, style="bold magenta")

    def report_failure(self, error: str) -> None:
        """Report migration failure."""
        print_prompt("❌ Migration failed!", style="bold red", logger=self.summary_logger, prefix="")
        print_prompt(f"💥 Error: {error}", style="bold red", logger=self.summary_logger, prefix="")
        print_prompt(
            "📚 Check logs for details and try again.", style="bold yellow", logger=self.summary_logger, prefix=""
        )
