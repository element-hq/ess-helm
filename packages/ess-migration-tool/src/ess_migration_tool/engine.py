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
from .models import ConfigMap, DiscoveredSecret, GlobalOptions, MigrationError, Secret
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
    global_options: GlobalOptions = field(default_factory=GlobalOptions)

    def __post_init__(self) -> None:
        """Initialize the migration engine."""
        for migration, secret_discovery_strategy, extra_file_strategy in [
            (SynapseMigration(self.global_options), SynapseSecretDiscovery(), SynapseExtraFileDiscovery()),
            (MASMigration(self.global_options), MASSecretDiscovery(), MASExtraFileDiscovery()),
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
                        global_options=self.global_options,
                    )
                )

    def prompt_for_database_choice(self) -> bool:
        """
        Prompt user to choose between using existing database or ESS-managed Postgres.

        Returns:
            True if user wants to use existing database, False for ESS-managed Postgres
        """
        self.pretty_logger.info("\n" + "=" * 60)
        self.pretty_logger.info("🗃️  DATABASE CONFIGURATION CHOICE")
        self.pretty_logger.info("=" * 60)
        self.pretty_logger.info("How would you like to handle the database for your ESS deployment?")
        self.pretty_logger.info("")
        self.pretty_logger.info("1. 🔗 Connect to existing database (recommended for production)")
        self.pretty_logger.info("   - Import your current database settings into ESS")
        self.pretty_logger.info("   - Continue using your existing PostgreSQL instance")
        self.pretty_logger.info("")
        self.pretty_logger.info("2. 🆕 Install Postgres with ESS and import database later")
        self.pretty_logger.info("   - Let ESS deploy and manage PostgreSQL")
        self.pretty_logger.info("   - Import your Synapse and MAS database schemas after deployment")
        self.pretty_logger.info("   - Recommended for testing/new installations")
        self.pretty_logger.info("")

        while True:
            try:
                choice = input("   Please select an option [1/2] (default: 1): ").strip()
                if choice == "" or choice == "1":
                    self.pretty_logger.info("   ✅ Using existing database configuration")
                    return True
                elif choice == "2":
                    self.pretty_logger.info("   ✅ Using ESS-managed Postgres (import database later)")
                    return False
                else:
                    self.pretty_logger.info("   ❌ Invalid choice. Please enter 1 or 2.")
            except KeyboardInterrupt as err:
                self.pretty_logger.info("\n   ❌ Operation cancelled by user")
                raise MigrationError("User cancelled database choice") from err
            except EOFError as err:
                self.pretty_logger.info("\n   ❌ End of input reached")
                raise MigrationError("End of input during database choice") from err

    def run_migration(self) -> dict[str, Any]:
        """
        Main migration entry point that orchestrates the entire process.

        Returns:
            ESS values dictionary
        """
        logger.info("Starting migration process")

        # Prompt for database choice
        self.global_options.use_existing_database = self.prompt_for_database_choice()

        for migrator in self.migrators:
            migrator.migrate()

            # Collect override warnings
            self.override_warnings.extend(migrator.override_warnings)
            self.discovered_secrets.extend(migrator.discovered_secrets)
            self.init_by_ess_secrets.extend(migrator.init_by_ess_secrets)

        logger.info("Migration process completed successfully")
        return self.ess_config
