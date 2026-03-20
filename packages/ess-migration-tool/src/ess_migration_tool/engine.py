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
from .mas import MASExtraFileDiscovery, MASMigration, MASSecretDiscovery
from .migration import MigrationService
from .models import ConfigMap, DiscoveredSecret, Secret
from .synapse import SynapseExtraFileDiscovery, SynapseMigration, SynapseSecretDiscovery

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
    discovered_secrets: list[DiscoveredSecret] = field(default_factory=list)
    init_by_ess_secrets: list[str] = field(default_factory=list)
    migrators: list[MigrationService] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize the migration engine."""
        for migration, secret_discovery_strategy, extra_file_strategy in [
            (SynapseMigration(), SynapseSecretDiscovery(), SynapseExtraFileDiscovery()),
            (MASMigration(), MASSecretDiscovery(), MASExtraFileDiscovery()),
        ]:
            migration_input = self.input_processor.input_for_component(migration.component_root_key)
            if migration_input:
                self.migrators.append(
                    MigrationService(
                        input=migration_input,
                        ess_config=self.ess_config,
                        pretty_logger=self.pretty_logger,
                        migration=migration,
                        secrets=self.secrets,
                        secret_discovery_strategy=secret_discovery_strategy,
                        configmaps=self.configmaps,
                        extra_files_strategy=extra_file_strategy,
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
            self.discovered_secrets.extend(migrator.discovered_secrets)
            self.init_by_ess_secrets.extend(migrator.init_by_ess_secrets)

        # Handle component-specific relationships after migration
        migrated_components = {migrator.component_root_key for migrator in self.migrators}

        # Define all known ESS components
        # These are components that can be managed by ESS Helm chart
        ALL_ESS_COMPONENTS = {"synapse", "matrixAuthenticationService", "elementWeb", "elementAdmin", "matrixRTC"}

        # Disable any ESS component that was not migrated
        for component in ALL_ESS_COMPONENTS:
            if component not in migrated_components:
                self.ess_config.setdefault(component, {})["enabled"] = False

        logger.info("Migration process completed successfully")
        return self.ess_config
