# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Input processing module for the migration script.
Handles loading and parsing of configuration files.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import MigrationError, MigrationInput
from .well_known import WELL_KNOWN_FILE_PATTERNS, WELL_KNOWN_STRATEGY_NAMES

logger = logging.getLogger("migration")


class ValidationError(MigrationError):
    """Exception for input validation failures."""

    pass


@dataclass
class InputProcessor:
    """Handles loading and parsing of input configuration files."""

    inputs: list[MigrationInput] = field(default_factory=list)

    def input_for_strategy(self, strategy_name: str) -> MigrationInput | None:
        """
        Return the migration input for a strategy.

        Args:
            strategy_name: The user-facing strategy name (e.g., "Synapse", "Matrix Authentication Service")

        Returns:
            MigrationInput for the strategy, or None if not found
        """
        for _input in self.inputs:
            if _input.name == strategy_name:
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
    def load_json_file(path: str) -> dict[str, Any]:
        """
        Load and parse a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            Parsed JSON content as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON parsing fails
            ValidationError: If file validation fails
        """
        try:
            # Validate file exists and is readable
            InputProcessor._validate_file_path(path)

            with open(path, encoding="utf-8") as f:
                content = json.load(f) or {}

            # Validate JSON content is not empty for required files
            if not content:
                logger.warning(f"JSON file {path} is empty")

            return content
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON file {path}: {e}")
            raise ValidationError(f"Invalid JSON in file {path}: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load JSON file {path}: {e}")
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
        # Determine file type by extension and use appropriate loader
        file_path = Path(config_path)
        if file_path.suffix.lower() == ".json":
            config = InputProcessor.load_json_file(config_path)
        else:
            # Default to YAML for .yaml, .yml, or any other extension
            config = InputProcessor.load_yaml_file(config_path)

        logger.info(f"{name} : {config_path} loaded successfully")

        self.inputs.append(
            MigrationInput(
                name=name,
                config_path=config_path,
                config=config,
            )
        )

    def load_well_known_inputs(
        self,
        dir_path: str | None = None,
        client_path: str | None = None,
        server_path: str | None = None,
        support_path: str | None = None,
    ) -> None:
        """Load well-known delegation files as migration inputs."""
        file_results = self._load_well_known_files(dir_path, client_path, server_path, support_path)

        for strategy_name, source_path, config in file_results:
            self.inputs.append(
                MigrationInput(
                    name=strategy_name,
                    config_path=source_path,
                    config=config,
                )
            )
            logger.info(f"{strategy_name}: loaded from {source_path}")

    @staticmethod
    def _load_well_known_files(
        dir_path: str | None = None,
        client_path: str | None = None,
        server_path: str | None = None,
        support_path: str | None = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Load well-known delegation files from directory and/or individual paths.

        Args:
            dir_path: Path to directory containing well-known files
            client_path: Path to client or client.json file
            server_path: Path to server or server.json file
            support_path: Path to support or support.json file

        Returns:
            List of tuples: (strategy_name, source_path, config_dict)
            Only includes files that were found and loaded
        """
        results: list[tuple[str, str, dict[str, Any]]] = []

        # Mapping of CLI arg to well-known type
        arg_to_type = {
            client_path: "client",
            server_path: "server",
            support_path: "support",
        }

        # Load individual files from CLI args first (highest precedence)
        for arg_path, wk_type in arg_to_type.items():
            if arg_path:
                try:
                    config = InputProcessor.load_json_file(arg_path)
                    strategy_name = WELL_KNOWN_STRATEGY_NAMES[wk_type]
                    results.append((strategy_name, arg_path, config))
                except Exception as e:
                    logger.warning(f"Failed to load {wk_type} file {arg_path}: {e}")

        # Load from directory (lower precedence, only if not already loaded via CLI arg)
        if dir_path:
            dir_path_obj = Path(dir_path)
            loaded_strategies: set[str] = {r[0] for r in results}

            for wk_type, file_names in WELL_KNOWN_FILE_PATTERNS.items():
                strategy_name = WELL_KNOWN_STRATEGY_NAMES[wk_type]
                if strategy_name in loaded_strategies:
                    continue

                for file_name in file_names:
                    file_path = dir_path_obj / file_name
                    if file_path.is_file():
                        try:
                            config = InputProcessor.load_json_file(str(file_path))
                            results.append((strategy_name, str(file_path), config))
                            break
                        except Exception as e:
                            logger.warning(f"Failed to load {file_name} from directory: {e}")
                            break

        return results
