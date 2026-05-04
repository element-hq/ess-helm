# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration engine that orchestrates the conversion process.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from .element_web import ElementWebMigration
from .extra_files import GenericExtraFileDiscovery
from .inputs import InputProcessor
from .mas import MASExtraFileDiscovery, MASMigration, MASSecretDiscovery
from .migration import MigrationService
from .models import ConfigMap, DiscoveredSecret, GlobalOptions, Secret, ValueSourceTracking
from .synapse import SynapseExtraFileDiscovery, SynapseMigration, SynapseSecretDiscovery
from .utils import resolve_value_conflicts

logger = logging.getLogger("migration")


@dataclass
class MigrationEngine:
    """Core migration engine that handles the conversion process."""

    input_processor: InputProcessor = field(init=True)
    pretty_logger: logging.Logger = field(init=True)
    ess_config: dict[str, Any] = field(default_factory=dict)
    secrets: list[Secret] = field(default_factory=list)
    configmaps: list[ConfigMap] = field(default_factory=list)
    override_warnings: list[str] = field(default_factory=list)
    underride_warnings: list[str] = field(default_factory=list)
    discovered_secrets: list[DiscoveredSecret] = field(default_factory=list)
    init_by_ess_secrets: list[str] = field(default_factory=list)
    migrators: list[MigrationService] = field(default_factory=list)
    global_options: GlobalOptions = field(default_factory=GlobalOptions)
    value_source_tracking: ValueSourceTracking = field(default_factory=ValueSourceTracking)

    def __post_init__(self) -> None:
        """Initialize the migration engine."""
        components = [
            (
                SynapseMigration(self.global_options),
                SynapseSecretDiscovery(self.global_options),
                SynapseExtraFileDiscovery(),
            ),
            (
                MASMigration(self.global_options),
                MASSecretDiscovery(self.global_options),
                MASExtraFileDiscovery(),
            ),
            (
                ElementWebMigration(self.global_options),
                None,
                GenericExtraFileDiscovery(component_name="Element Web", component_root_key="elementWeb"),
            ),
        ]
        for migration, secret_discovery_strategy, extra_file_strategy in components:
            strategy_name = migration.name
            migration_input = self.input_processor.input_for_strategy(strategy_name)
            if migration_input:
                self.migrators.append(
                    MigrationService(
                        input=migration_input,
                        pretty_logger=self.pretty_logger,
                        ess_config=self.ess_config,
                        migration=migration,
                        extra_files_strategy=extra_file_strategy,
                        secret_discovery_strategy=secret_discovery_strategy,
                        secrets=self.secrets,
                        configmaps=self.configmaps,
                        global_options=self.global_options,
                    )
                )

    def run_migration(self) -> dict[str, Any]:
        """
        Main migration entry point that orchestrates the entire process.

        Returns:
            ESS values dictionary
        """
        logger.info("Starting migration process")
        for migrator in self.migrators:
            migrator.migrate()

            # Collect override and underride warnings, secrets, and value sources
            self.override_warnings.extend(migrator.override_warnings)
            self.underride_warnings.extend(migrator.underride_warnings)
            self.discovered_secrets.extend(migrator.discovered_secrets)
            self.init_by_ess_secrets.extend(migrator.init_by_ess_secrets)

            # Collect value sources from this migrator
            for path, sources in migrator.value_source_tracking.sources.items():
                for source in sources:
                    self.value_source_tracking.add_source(path, source.strategy_name, source.value, source.source_path)

        # Resolve conflicts after all migrations
        resolve_value_conflicts(self.pretty_logger, self.value_source_tracking, self.ess_config)

        # Disable any ESS component that was not migrated (absent from config)
        ALL_ESS_COMPONENTS = {"synapse", "matrixAuthenticationService", "elementWeb", "elementAdmin", "matrixRTC"}
        for component in ALL_ESS_COMPONENTS:
            if component not in self.ess_config:
                self.ess_config[component] = {"enabled": False}

        logger.info("Migration process completed successfully")
        return self.ess_config
