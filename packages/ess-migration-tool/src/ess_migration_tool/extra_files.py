# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Extra files handling module for the migration script.
Handles discovery, reading, and validation of extra files from configuration files.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from .models import DiscoveredExtraFile, DiscoveredPath, SecretConfig
from .utils import is_quiet_mode, prompt_choice, prompt_value, prompt_yes_no

logger = logging.getLogger("migration")


class ExtraFilesError(Exception):
    """Base exception for extra files-related errors."""

    pass


def ess_schema_config_key_secret_paths(ess_schema: dict[str, SecretConfig]):
    return [secret_config.config_path for secret_config in ess_schema.values() if secret_config.config_path is not None]


@dataclass
class ExtraFilesDiscovery:
    """Handles discovery and extraction of extra files from configuration files."""

    pretty_logger: logging.Logger = field(init=True)
    strategy: ExtraFilesDiscoveryStrategy = field(init=True)  # Strategy for component-specific secret discovery
    secrets_strategy: SecretDiscoveryStrategy | None = field(
        init=True
    )  # Strategy for component-specific secret discovery
    source_file: str = field(init=True)  # Source file path
    discovered_extra_files: dict[Path, DiscoveredExtraFile] = field(
        default_factory=dict
    )  # Discovered Extra File to mount in ESS
    discovered_file_paths: list[DiscoveredPath] = field(default_factory=list)  # File paths discovered in configuration
    skipped_config_keys: list[str] = field(default_factory=list)  # Configuration keys that are skipped

    @property
    def missing_file_paths(self) -> list[DiscoveredPath]:
        """
        Get a list of missing file paths.
        """
        return [
            fp
            for fp in self.discovered_file_paths
            if not fp.skipped_reason
            and fp
            not in [
                discovered_source_path
                for exf in self.discovered_extra_files.values()
                for discovered_source_path in exf.discovered_source_paths
            ]
        ]

    def discover_extra_files_from_config(self, config_data: dict) -> None:
        """
        Discover extra file paths from configuration data.

        Args:
            config_data: Configuration dictionary to analyze
            ignored_config_keys: List of configuration keys where file paths should be ignored
        """
        logger.info("Discovering extra files configuration")

        # Check for common file path patterns in the config dict
        self._discover_file_paths_from_list_or_dict(config_data)

        # Run an initial lookup of files at the paths discovered
        self._discover_extra_files()

    def _discover_file_paths_from_list_or_dict(self, config_data: dict | list, parent_key: str = "") -> None:
        """
        Recursively discover file paths from dictionary data.

        Args:
            config_data: Configuration dictionary to analyze
            parent_key: Parent key path for nested configurations
        """
        if isinstance(config_data, list):
            # Build the full key path
            if not parent_key:
                raise RuntimeError("ESS Migration does not handle source file with only a single list at root")
            # Skip if parent_key is in ignored config keys
            # This prevents discovery of file paths in ignored sections (e.g., secrets.keys)
            if parent_key in self.strategy.ignored_config_keys:
                return
            for i, value in enumerate(config_data):
                full_key = f"{parent_key}.{i}"
                if isinstance(value, str) and self._is_file_path(value):
                    # This is a regular extra file
                    self.discovered_file_paths.append(
                        DiscoveredPath(
                            config_key=full_key,
                            source_file=self.source_file,
                            source_path=Path(value),
                        )
                    )
                elif isinstance(value, (dict, list)):
                    # Recursively check nested dictionaries with updated key path
                    self._discover_file_paths_from_list_or_dict(value, full_key)
        else:
            for key, value in config_data.items():
                # Build the full key path
                full_key = f"{parent_key}.{key}" if parent_key else key
                if isinstance(value, str) and self._is_file_path(value):
                    skipped_reason = None
                    # Check if this key exactly matches any secret configuration paths
                    if self.secrets_strategy and full_key in ess_schema_config_key_secret_paths(
                        self.secrets_strategy.ess_secret_schema
                    ):
                        skipped_reason = f"{key} = {value} is already managed by secret"
                        logger.info(f"Skipping {key} = {value}")
                    elif full_key in self.strategy.ignored_config_keys:
                        skipped_reason = f"{key} = {value} contains file we do not want to import in a ConfigMap"
                        logger.info(f"Skipping {key} = {value}")
                    # This is a regular extra file
                    self.discovered_file_paths.append(
                        DiscoveredPath(
                            config_key=full_key,
                            source_file=self.source_file,
                            source_path=Path(value),
                            skipped_reason=skipped_reason,
                        )
                    )
                elif isinstance(value, (dict, list)):
                    # Recursively check nested dictionaries with updated key path
                    self._discover_file_paths_from_list_or_dict(value, full_key)

    def _is_file_path(self, value: str) -> bool:
        """
        Check if a string value looks like a file path.

        Args:
            value: String value to check

        Returns:
            True if the value looks like a file path
        """
        # is the value has a scheme, skip it
        if urlparse(value).scheme:
            return False

        # Check for common file path patterns
        patterns = [
            r"^/[^/].*",  # Absolute path starting with /
            r"\./.*",  # Relative path starting with ./
            r"\.\./.*",  # Relative path starting with ../
            r"~/.+",  # Home directory path
        ]

        return any(re.match(pattern, value) for pattern in patterns)

    def _discover_extra_files(self) -> None:
        """
        Discover extra files from discovered file paths.
        """
        logger.info("Discovering extra files")
        for _discovered_path in self.discovered_file_paths:
            if _discovered_path.skipped_reason:
                continue
            if _discovered_path.source_path.is_dir():
                files_in_dir = self._handle_directory(_discovered_path)
                logger.info(f"Found {len(files_in_dir)} files in directory {_discovered_path.source_path}")
                self.pretty_logger.info(
                    f"📁 Found {len(files_in_dir)} files in directory: {_discovered_path.source_path}"
                )
                # Show the files being imported
                for file_path in files_in_dir:
                    logger.info(f"  - {file_path}")
                    self.pretty_logger.info(f"  📄 {Path(file_path).name}")
                if not files_in_dir:
                    logger.warning(f"No files found in directory: {_discovered_path.source_path}")
                    self.pretty_logger.info(f"⚠️  No files found in directory: {_discovered_path.source_path}")
            else:
                if _discovered_path.source_path not in self.discovered_extra_files:
                    try:
                        # If the file is not matching an existing extra file, add it to the discovered extra files
                        self.discovered_extra_files[_discovered_path.source_path] = self._discover_extra_file(
                            _discovered_path
                        )
                    except ExtraFilesError as e:
                        logger.error(f"Failed to process file {_discovered_path.source_path}: {e}")

    def _handle_directory(self, discovered_path: DiscoveredPath, override_path: Path | None = None) -> list[str]:
        """
        Handle directory by importing files non-recursively.

        Args:
            discovered_path: Path to the directory to process
        """
        logger.info(f"Processing directory: {discovered_path.source_path}")

        # Get all files in the directory (non-recursive)
        discovered_path.is_dir = True
        try:
            files_in_dir = []
            list_path = Path(discovered_path.source_path)
            if override_path:
                list_path = override_path
            for item in list_path.iterdir():
                if item.is_file():
                    files_in_dir.append(str(item))
                    try:
                        extra_file = self._discover_extra_file(discovered_path, item)
                        if extra_file:
                            self.discovered_extra_files[item] = extra_file
                    except ExtraFilesError as e:
                        logger.error(f"Failed to process file {item}: {e}")

            return files_in_dir

        except Exception as e:
            logger.error(f"Failed to process directory {discovered_path}: {e}")
            raise ExtraFilesError(f"Failed to process directory {discovered_path}: {e}") from e

    def prompt_for_missing_files(self) -> None:
        """
        Prompt user for alternative paths when files are missing.
        """
        # Check if quiet mode is enabled
        if is_quiet_mode(self.pretty_logger) and self.missing_file_paths:
            missing_files = [str(fp.source_path) for fp in self.missing_file_paths]
            raise ExtraFilesError(
                f"Missing extra files in quiet mode: {', '.join(missing_files)}. "
                "Cannot prompt for files when --quiet is enabled."
            )

        self.pretty_logger.info("\n" + "=" * 60)
        self.pretty_logger.info("📁 EXTRA FILES DISCOVERY")
        self.pretty_logger.info("=" * 60)
        if self.missing_file_paths:
            self.pretty_logger.info("The following extra files were referenced in your configuration")
            self.pretty_logger.info("but could not be found:")

        for file_path in self.missing_file_paths:
            self.pretty_logger.info(f"📝 Missing: {file_path.config_key} ({file_path.source_path})")

            self.pretty_logger.info("\n🔍 Would you like to:")
            self.pretty_logger.info("  1. Provide alternative path for this file")
            self.pretty_logger.info("  2. Skip these files and continue")
            self.pretty_logger.info("  3. Provide a directory to search for files")

            choice = prompt_choice(
                self.pretty_logger,
                "Enter your choice (1/2/3):",
                [
                    "Provide alternative path for this file",
                    "Skip these files and continue",
                    "Provide a directory to search for files",
                ],
            )

            if choice == "Provide alternative path for this file":
                # Provide alternative paths
                self._prompt_for_individual_alternatives(file_path)
            elif choice == "Skip these files and continue":
                # Skip missing files
                self.pretty_logger.info("   ⚠️  Skipping missing files...")
                file_path.skipped_reason = "Skipped by user"
            elif choice == "Provide a directory to search for files":
                # Provide directory to search
                self._prompt_for_directory_search(file_path)

    def _prompt_for_individual_alternatives(self, discovered_path: DiscoveredPath) -> None:
        """
        Prompt user for alternative paths for each missing file.
        """

        def validate_file_path(path: str) -> tuple[bool, str]:
            if path.lower() == "skip":
                return True, ""  # Special case for skip
            if not path:
                return False, "File path cannot be empty. Please try again."
            try:
                new_path_obj = Path(path)
                if new_path_obj.is_dir():
                    return False, "Targetted file is a directory."
                discovered_extra_file = self._discover_extra_file(discovered_path, new_path_obj)
                if not discovered_extra_file:
                    return False, "File not found or invalid."
                return True, ""
            except ExtraFilesError as e:
                return False, str(e)

        while True:
            new_path = prompt_value(
                self.pretty_logger,
                "Please enter the correct file path (or 'skip' to ignore):",
                validator=validate_file_path,
            )

            if new_path.lower() == "skip":
                self.pretty_logger.info(f"   ⚠️  Skipping file: {discovered_path.source_path}")
                break

            new_path_obj = Path(new_path)
            discovered_extra_file = self._discover_extra_file(discovered_path, new_path_obj)
            if discovered_extra_file:
                self.discovered_extra_files[new_path_obj] = discovered_extra_file
                self.pretty_logger.info(f"   ✅ File validated: {new_path}")
                break

    def _prompt_for_directory_search(self, discovered_path: DiscoveredPath) -> None:
        """
        Prompt user for a directory to search for missing files.
        """
        self.pretty_logger.info("\n📁 Please provide a directory to search for missing files:")

        def validate_directory(path: str) -> tuple[bool, str]:
            if not path:
                return False, "Directory path cannot be empty. Please try again."
            try:
                dir_path = Path(path)
                if not dir_path.is_dir():
                    return False, f"Path is not a directory: {path}"
                return True, ""
            except Exception as e:
                return False, str(e)

        while True:
            search_dir = prompt_value(
                self.pretty_logger,
                "Enter directory path:",
                validator=validate_directory,
            )

            dir_path = Path(search_dir)

            # Search for missing files in the directory
            found_files = self._handle_directory(discovered_path, dir_path)

            if found_files:
                self.pretty_logger.info(f"   ✅ Found {len(found_files)} matching files in {search_dir}")
                for file_path in found_files:
                    self.pretty_logger.info(f"      📄 {Path(file_path).name}")
                break
            else:
                self.pretty_logger.info(f"   ⚠️  No matching files found in {search_dir}")
                self.pretty_logger.info("   Would you like to try another directory?")
                retry = prompt_yes_no(
                    self.pretty_logger,
                    "Try another directory?",
                    default=False,
                )
                if not retry:
                    self.pretty_logger.info("   ⚠️  Skipping directory search...")
                    break

    def validate_extra_files(self) -> None:
        """
        Revalidate files after user prompting.
        """
        # If we still have missing files after prompting, raise an error
        if self.missing_file_paths:
            missing_list = ", ".join([str(missing.source_path) for missing in self.missing_file_paths])
            raise ExtraFilesError(f"Missing or invalid extra files: {missing_list}")

        self.pretty_logger.info("\n✅ Extra files validation completed")
        self.pretty_logger.info("=" * 60)

    def _is_binary_file(self, path: Path) -> bool:
        """
        Detect if a file is binary by checking for null bytes.

        Args:
            path: Path to the file to check

        Returns:
            True if the file appears to be binary, False otherwise
        """
        try:
            with open(path, "rb") as f:
                # Read a sample of the file (first 1024 bytes)
                sample = f.read(1024)
                # Check for null bytes which are common in binary files
                return b"\x00" in sample
        except Exception as e:
            logger.warning(f"Could not determine if file {path} is binary: {e}")
            return False

    def _discover_extra_file(
        self, discovered_path: DiscoveredPath, override_path: Path | None = None
    ) -> DiscoveredExtraFile:
        """
        Validate that a file path exists and is readable.

        Args:
            path: Path to validate

        Returns:
            True if file is valid, False if it's a binary file

        Raises:
            ExtraFilesError: If file doesn't exist or isn't readable
        """
        file_path = override_path or Path(discovered_path.source_path)
        extra_file = DiscoveredExtraFile(filename=file_path.name, discovered_source_paths=[discovered_path])

        if not file_path.exists():
            raise ExtraFilesError(f"Extra file does not exist: {file_path}")

        if not file_path.is_file():
            raise ExtraFilesError(f"Extra file path is not a file: {file_path}")

        # Check if file is binary
        if self._is_binary_file(file_path):
            extra_file.cleartext = False

        try:
            with open(file_path):
                extra_file.content = file_path.read_bytes()
        except PermissionError as err:
            raise ExtraFilesError(f"Permission denied when reading file: {file_path}") from err
        return extra_file


class GenericExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    """Generic extra file discovery for components without special rules."""

    def __init__(
        self,
        component_name: str,
        component_root_key: str,
        ignored_config_keys: list[str] | None = None,
        ignored_file_paths: list[str] | None = None,
    ):
        self._component_name = component_name
        self._component_root_key = component_root_key
        self._ignored_config_keys = ignored_config_keys or []
        self._ignored_file_paths = ignored_file_paths or []

    @property
    def component_name(self) -> str:
        return self._component_name

    @property
    def component_root_key(self) -> str:
        return self._component_root_key

    @property
    def ignored_config_keys(self) -> list[str]:
        return self._ignored_config_keys

    @property
    def ignored_file_paths(self) -> list[str]:
        return self._ignored_file_paths
