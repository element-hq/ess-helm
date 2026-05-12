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
from .hookshot import HookshotExtraFileDiscovery, HookshotMigration, HookshotSecretDiscovery
from .inputs import InputProcessor
from .mas import MASExtraFileDiscovery, MASMigration, MASSecretDiscovery
from .migration import MigrationService
from .models import ConfigMap, DiscoveredSecret, GlobalOptions, Secret, ValueSourceTracking
from .synapse import SynapseExtraFileDiscovery, SynapseMigration, SynapseSecretDiscovery
from .utils import resolve_value_conflicts
from .well_known import WELL_KNOWN_COMPONENT_ROOT_KEY, WellKnownMigration

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
            (
                WellKnownMigration(self.global_options, well_known_type="client"),
                None,
                GenericExtraFileDiscovery(
                    component_name="Well Known Client",
                    component_root_key=WELL_KNOWN_COMPONENT_ROOT_KEY,
                ),
            ),
            (
                WellKnownMigration(self.global_options, well_known_type="server"),
                None,
                GenericExtraFileDiscovery(
                    component_name="Well Known Server",
                    component_root_key=WELL_KNOWN_COMPONENT_ROOT_KEY,
                ),
            ),
            (
                WellKnownMigration(self.global_options, well_known_type="support"),
                None,
                GenericExtraFileDiscovery(
                    component_name="Well Known Support",
                    component_root_key=WELL_KNOWN_COMPONENT_ROOT_KEY,
                ),
            ),
            (
                HookshotMigration(self.global_options),
                HookshotSecretDiscovery(self.global_options),
                HookshotExtraFileDiscovery(),
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
                        value_source_tracking=self.value_source_tracking,
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

            # Collect override and underride warnings, secrets
            self.override_warnings.extend(migrator.override_warnings)
            self.underride_warnings.extend(migrator.underride_warnings)
            if migrator.secret_discovery:
                self.discovered_secrets.extend(migrator.secret_discovery.discovered_secrets.values())
                self.init_by_ess_secrets.extend(migrator.secret_discovery.init_by_ess_secrets)

        # Filter out any secrets that were actually discovered by any strategy
        # This ensures that secrets which were discovered (even by a different strategy)
        # are not in the final init_by_ess_secrets list
        all_discovered_keys = {secret.secret_key for secret in self.discovered_secrets}
        self.init_by_ess_secrets = [key for key in self.init_by_ess_secrets if key not in all_discovered_keys]

        # Prompt for missing secrets and validate after all strategies have resolved their secrets
        # This allows strategies to find secrets that previous strategies may have missed
        for migrator in self.migrators:
            if migrator.secret_discovery:
                migrator.secret_discovery.prompt_for_missing_secrets()
                migrator.secret_discovery.validate_required_secrets()
                # Handle any secrets that were just prompted for
                migrator.handle_secrets_phase()

        # Resolve conflicts after all migrations
        resolve_value_conflicts(self.pretty_logger, self.value_source_tracking, self.ess_config)

        # Disable any ESS component that was not migrated (absent from config)
        ALL_ESS_COMPONENTS = {
            "synapse",
            "matrixAuthenticationService",
            "elementWeb",
            "elementAdmin",
            "matrixRTC",
            "hookshot",
        }
        for component in ALL_ESS_COMPONENTS:
            if component not in self.ess_config:
                self.ess_config[component] = {"enabled": False}

        logger.info("Migration process completed successfully")
        return self.ess_config
