# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration engine that orchestrates the conversion process.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from .inputs import InputProcessor
from .migration import MigrationService
from .synapse import SynapseMigration

logger = logging.getLogger("migration")


@dataclass
class MigrationEngine:
    """Core migration engine that handles the conversion process."""

    input_processor: InputProcessor = field(init=True)
    ess_config: dict[str, Any] = field(default_factory=dict)
    override_warnings: list[str] = field(default_factory=list)
    migrators: list[MigrationService] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize the migration engine."""
        for migration in [SynapseMigration()]:
            self.migrators.append(
                MigrationService(
                    input=self.input_processor.input_for_component(migration.component_root_key),
                    ess_config=self.ess_config,
                    migration=migration,
                )
            )

    def run_migration(self) -> dict[str, Any]:
        """
        Main migration entry point that orchestrates the entire process.

        Returns:
            ESS values dictionary
        """
        logger.info("Starting migration process")

        # Initialize the ESS config with basic structure
        for migrator in self.migrators:
            migrator.migrate()

            # Collect override warnings
            self.override_warnings.extend(migrator.override_warnings)

        logger.info("Migration process completed successfully")
        return self.ess_config
