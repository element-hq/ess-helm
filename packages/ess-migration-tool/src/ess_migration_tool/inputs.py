# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Input processing module for the migration script.
Handles loading and parsing of configuration files.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import MigrationError, MigrationInput

logger = logging.getLogger("migration")


class ValidationError(MigrationError):
    """Exception for input validation failures."""

    pass


@dataclass
class InputProcessor:
    """Handles loading and parsing of input configuration files."""

    inputs: list[MigrationInput] = field(default_factory=list)

    def input_for_component(self, component_root_key: str) -> MigrationInput | None:
        """
        Return the migration input for a component.
        """
        for _input in self.inputs:
            if _input.name == component_root_key:
                return _input
        return None

    @staticmethod
    def load_yaml_file(path: str) -> dict[str, Any]:
        """
        Load and parse a YAML file.

        Args:
            path: Path to the YAML file

        Returns:
            Parsed YAML content as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValidationError: If file validation fails
        """
        try:
            # Validate file exists and is readable
            InputProcessor._validate_file_path(path)

            with open(path, encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}

            # Validate YAML content is not empty for required files
            if not content:
                logger.warning(f"YAML file {path} is empty")

            return content
        except Exception as e:
            logger.error(f"Failed to load YAML file {path}: {e}")
            raise

    @staticmethod
    def _validate_file_path(path: str) -> None:
        """
        Validate that a file path exists and is readable.

        Args:
            path: Path to validate

        Raises:
            ValidationError: If file doesn't exist or isn't readable
        """
        file_path = Path(path)

        if not file_path.exists():
            raise ValidationError(f"File does not exist: {path}")

        if not file_path.is_file():
            raise ValidationError(f"Path is not a file: {path}")

        if not file_path.stat().st_size > 0:
            logger.warning(f"File is empty: {path}")

        # Check read permissions
        try:
            with open(path):
                pass  # Just test opening
        except PermissionError as err:
            raise ValidationError(f"No read permission for file: {path}") from err

    def load_migration_input(
        self,
        name: str,
        config_path: str,
    ) -> None:
        """
        Main method to load all migration input data.

        Args:
            name: Name of the migration input
            config_path: Path to configuration file

        Raises:
            ValidationError: If input validation fails
            Exception: If any file loading fails
        """
        # Load configuration
        config = InputProcessor.load_yaml_file(config_path)

        logger.info(f"{name} : {config_path} loaded successfully")

        self.inputs.append(
            MigrationInput(
                name=name,
                config_path=config_path,
                config=config,
            )
        )
