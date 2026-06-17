# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Migration engine that orchestrates the conversion process.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import chain
from typing import Any

from .conflicts import DiscoveredSecretTracking, resolve_value_conflicts
from .element_web import ElementWebMigration
from .extra_files import GenericExtraFileDiscovery
from .hookshot import HookshotExtraFileDiscovery, HookshotMigration, HookshotSecretDiscovery
from .inputs import InputProcessor
from .interfaces import DataMigrationProtocol
from .mas import MASDataMigrationInstructions, MASExtraFileDiscovery, MASMigration, MASSecretDiscovery
from .migration import MigrationService
from .models import ConfigMap, DiscoveredSecret, GlobalOptions, Secret, ValueSourceTracking
from .rich_output import log_command
from .synapse import (
    SynapseDataMigrationInstructions,
    SynapseExtraFileDiscovery,
    SynapseMigration,
    SynapseSecretDiscovery,
)
from .utils import press_enter_to_continue, print_prompt, print_section
from .well_known import WELL_KNOWN_COMPONENT_ROOT_KEY, WellKnownMigration

logger = logging.getLogger("migration")


@dataclass
class MigrationEngine:
    """Core migration engine that handles the conversion process."""

    input_processor: InputProcessor = field(init=True)
    summary_logger: logging.Logger = field(init=True)
    global_options: GlobalOptions = field(init=True)
    ess_config: dict[str, Any] = field(default_factory=dict)
    secrets: list[Secret] = field(default_factory=list)
    configmaps: list[ConfigMap] = field(default_factory=list)
    override_warnings: list[str] = field(default_factory=list)
    underride_warnings: list[str] = field(default_factory=list)
    discovered_secrets: list[DiscoveredSecret] = field(default_factory=list)
    init_by_ess_secrets: list[str] = field(default_factory=list)
    migrators: list[MigrationService] = field(default_factory=list)
    data_migration_protocols: list[DataMigrationProtocol] = field(default_factory=list)
    value_source_tracking: ValueSourceTracking = field(default_factory=ValueSourceTracking)
    secret_tracking: DiscoveredSecretTracking = field(default_factory=DiscoveredSecretTracking)

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
                        summary_logger=self.summary_logger,
                        ess_config=self.ess_config,
                        migration=migration,
                        extra_files_strategy=extra_file_strategy,
                        secret_discovery_strategy=secret_discovery_strategy,
                        secrets=self.secrets,
                        configmaps=self.configmaps,
                        global_options=self.global_options,
                        value_source_tracking=self.value_source_tracking,
                        secret_tracking=self.secret_tracking,
                    )
                )
        self.data_migration_protocols = [
            SynapseDataMigrationInstructions(self.global_options),
            MASDataMigrationInstructions(self.global_options),
        ]

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

        # Resolve secret conflicts after all migrations
        self.secret_tracking.resolve_secret_conflicts(self.summary_logger, self.global_options)

        # Prompt for missing secrets and validate after all strategies have resolved their secrets
        # This allows strategies to find secrets that previous strategies may have missed
        for migrator in self.migrators:
            if migrator.secret_discovery:
                migrator.secret_discovery.prompt_for_missing_secrets()
                migrator.secret_discovery.validate_required_secrets()
                # Handle any secrets that were just prompted for
                migrator.handle_secrets_phase()

        # Resolve value conflicts after all migrations
        resolve_value_conflicts(self.summary_logger, self.value_source_tracking, self.ess_config, self.global_options)

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

    def manual_procedure(self, step_number: int) -> None:
        def _print_steps_with_generator(steps_title: str, instructions_generator: Iterator[str], conclusion: str = ""):
            nonlocal step_number
            first_instruct = next(instructions_generator, None)

            if first_instruct is not None:
                print_prompt(
                    steps_title,
                    style="default",
                    logger=self.summary_logger,
                )
                log_command(first_instruct, logger=self.summary_logger)
                for instruct in instructions_generator:
                    log_command(instruct, logger=self.summary_logger)
                if conclusion:
                    print_prompt(conclusion, style="default", logger=self.summary_logger)
                press_enter_to_continue(self.summary_logger, self.global_options)
                step_number += 1

        def _data_migration_generator() -> Iterator[tuple[DataMigrationProtocol, dict[str, Any]]]:
            for data_migration in self.data_migration_protocols:
                input_for_migration = self.input_processor.input_for_strategy(data_migration.component_name)
                if input_for_migration:
                    yield data_migration, input_for_migration.config

        _print_steps_with_generator(
            f"{step_number}. Stop ESS Pro workloads before importing:",
            chain.from_iterable(data_migration.stop_in_ess_pro() for data_migration, _ in _data_migration_generator()),
        )

        _print_steps_with_generator(
            f"{step_number}. Copy media from your existing setup to ESS persistent volume:",
            chain.from_iterable(
                data_migration.run_media_migration(source_config)
                for data_migration, source_config in _data_migration_generator()
            ),
            "📚 For more details on deployment and data migration, refer to the ESS documentation.",
        )

        # Add database-specific instructions
        if not self.global_options.use_existing_database:
            print_section("📋 DATABASE IMPORT INSTRUCTIONS", logger=self.summary_logger)
            print_prompt(
                "Since you chose to use ESS-managed PostgreSQL, you'll need to import your "
                "existing database schema after deployment. Here are the steps:",
                style="default",
                logger=self.summary_logger,
            )
            press_enter_to_continue(self.summary_logger, self.global_options)

            _print_steps_with_generator(
                f"{step_number}. Create database dumps:",
                chain.from_iterable(
                    data_migration.create_db_dump(source_config)
                    for data_migration, source_config in _data_migration_generator()
                ),
            )
            _print_steps_with_generator(
                f"{step_number}. Copy the dumps to the ESS PostgreSQL pod:",
                chain.from_iterable(
                    data_migration.copy_db_dump_to_ess_pro() for data_migration, _ in _data_migration_generator()
                ),
            )
            _print_steps_with_generator(
                f"{step_number}. Import the dumps into the ESS-managed PostgreSQL:",
                chain.from_iterable(
                    data_migration.import_db_in_ess_pro() for data_migration, _ in _data_migration_generator()
                ),
            )

        _print_steps_with_generator(
            f"{step_number}. Start ESS Pro workloads again:",
            chain.from_iterable(
                data_migration.restart_in_ess_pro() for data_migration, _ in _data_migration_generator()
            ),
        )
