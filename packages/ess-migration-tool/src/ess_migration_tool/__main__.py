# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Main CLI entry point for the migration script.
"""

import argparse
import logging
import os

from .element_web import ELEMENT_WEB_STRATEGY_NAME
from .engine import MigrationEngine
from .hookshot import HOOKSHOT_STRATEGY_NAME
from .inputs import InputProcessor, ValidationError
from .mas import MAS_STRATEGY_NAME, parse_postgres_uri
from .outputs import generate_helm_values, write_outputs
from .rich_output import ProgressReporter, print_section, print_table
from .synapse import SYNAPSE_STRATEGY_NAME
from .utils import press_enter_to_continue, prompt_for_database_choice

LOADING_STEP = "Loading and validating input files"
MIGRATING_STEP = "Migrating configuration to ESS values"
GENERATING_VALUES_STEP = "Generating Helm values"
WRITING_OUTPUTS_STEP = "Writing output files"

logger = logging.getLogger("migration")


def main() -> int:
    """Main entry point for the migration CLI."""
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Migrate Matrix Stack configurations to Element Server Suite Helm values",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic migration with Synapse only
  python -m migration --synapse-config synapse.yaml

  # Verbose output for debugging
  python -m migration --synapse-config synapse.yaml --verbose
        """,
    )

    parser.add_argument(
        "--synapse-config",
        required=True,
        help=(
            "Path to Synapse homeserver.yaml configuration file. "
            "This is the main Synapse configuration that contains server_name, database, listeners, etc."
        ),
    )

    parser.add_argument(
        "--mas-config",
        required=False,
        help=("Path to Matrix Authentication Service config.yaml configuration file. "),
    )

    parser.add_argument(
        "--element-web-config",
        required=False,
        help=("Path to Element Web config.json configuration file. "),
    )

    parser.add_argument(
        "--well-known-dir",
        required=False,
        help=(
            "Path to directory containing well-known files "
            "(client, client.json, server, server.json, support, support.json)"
        ),
    )

    parser.add_argument(
        "--well-known-client",
        required=False,
        help=("Path to client or client.json well-known file"),
    )

    parser.add_argument(
        "--well-known-server",
        required=False,
        help=("Path to server or server.json well-known file"),
    )

    parser.add_argument(
        "--well-known-support",
        required=False,
        help=("Path to support or support.json well-known file"),
    )

    parser.add_argument(
        "--hookshot-config",
        required=False,
        help=("Path to Hookshot hookshot-config.yaml configuration file. "),
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help=(
            "Output directory for generated files (default: output). "
            "The migration will create Helm values.yaml and any ConfigMap files in this directory."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging. Shows detailed information about the migration process.",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging. Shows debug information about the migration process.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable migration summary output.",
    )

    parser.add_argument(
        "--database-mode",
        choices=["existing", "ess-managed"],
        help=(
            "Database migration mode. "
            "'existing' to use existing database, 'ess-managed' to use ESS-managed PostgreSQL. "
            "If not specified, user will be prompted."
        ),
    )

    # Parse arguments
    args = parser.parse_args()

    # Set up logging
    sh = logging.StreamHandler()
    logger.addHandler(sh)
    sh.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
        )
    )
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.CRITICAL)

    pretty_logger = logging.getLogger("migration:summary")
    pretty_logger.propagate = False
    pretty_logger.setLevel(logging.CRITICAL if args.quiet else logging.INFO)
    pretty_sh = logging.StreamHandler()
    # Use rich for colored output if available and not running in a test environment
    # RichHandler doesn't work well with pytest's capsys, so we detect pytest via PYTEST_CURRENT_TEST env var
    # Similar logic to press_enter_to_continue function in utils.py
    is_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    if not is_pytest:
        # Try to use rich for colored output
        try:
            from rich.logging import RichHandler

            pretty_handler = RichHandler(
                rich_tracebacks=False,
                show_time=False,
                show_level=False,
                show_path=False,
                enable_link_path=False,
            )
            pretty_logger.addHandler(pretty_handler)
        except ImportError:
            # Fallback to basic formatter if rich is not installed
            pretty_sh.setFormatter(
                logging.Formatter(
                    "%(message)s",
                )
            )
            pretty_logger.addHandler(pretty_sh)
    else:
        # Use basic formatter for pytest compatibility
        pretty_sh.setFormatter(
            logging.Formatter(
                "%(message)s",
            )
        )
        pretty_logger.addHandler(pretty_sh)

    # Set up progress reporter
    steps = [
        LOADING_STEP,
        MIGRATING_STEP,
        GENERATING_VALUES_STEP,
        WRITING_OUTPUTS_STEP,
    ]
    reporter = ProgressReporter(
        pretty_logger=pretty_logger,
        steps=steps,
        verbose=args.verbose,
    )

    try:
        reporter.start_migration()

        # Load migration input
        reporter.report_step(LOADING_STEP)
        input_processor = InputProcessor()
        input_processor.load_migration_input(
            name=SYNAPSE_STRATEGY_NAME,
            config_path=args.synapse_config,
        )

        if args.mas_config:
            input_processor.load_migration_input(
                name=MAS_STRATEGY_NAME,
                config_path=args.mas_config,
            )

        if args.element_web_config:
            input_processor.load_migration_input(
                name=ELEMENT_WEB_STRATEGY_NAME,
                config_path=args.element_web_config,
            )

        if args.well_known_dir or args.well_known_client or args.well_known_server or args.well_known_support:
            input_processor.load_well_known_inputs(
                dir_path=args.well_known_dir,
                client_path=args.well_known_client,
                server_path=args.well_known_server,
                support_path=args.well_known_support,
            )

        if args.hookshot_config:
            input_processor.load_migration_input(
                name=HOOKSHOT_STRATEGY_NAME,
                config_path=args.hookshot_config,
            )

        # Run migration
        reporter.report_step(MIGRATING_STEP)
        engine = MigrationEngine(input_processor=input_processor, pretty_logger=pretty_logger)

        # Set database mode if provided via command line
        if args.database_mode:
            if args.database_mode == "existing":
                engine.global_options.use_existing_database = True
            elif args.database_mode == "ess-managed":
                engine.global_options.use_existing_database = False
        else:
            # Prompt for database choice only if not already set via command line
            engine.global_options.use_existing_database = prompt_for_database_choice(pretty_logger)

        ess_values = engine.run_migration()

        # Generate outputs
        reporter.report_step(GENERATING_VALUES_STEP)
        helm_values = generate_helm_values(ess_values)

        # Write outputs
        reporter.report_step(WRITING_OUTPUTS_STEP)
        values_path, secret_paths, configmap_paths = write_outputs(
            helm_values=helm_values,
            secrets=engine.secrets,
            configmaps=engine.configmaps,
            output_dir=args.output_dir,
        )

        # Display migration summary
        press_enter_to_continue(pretty_logger)
        print_section("📊 MIGRATION SUMMARY", logger=pretty_logger)

        # Create a comprehensive mapping of source config paths to target ESS paths
        migration_mapping = {}

        # Process migrations
        for migrator in engine.migrators:
            # Get the input for this migrator's strategy
            # The input name is the same as the strategy name
            migration_input = engine.input_processor.input_for_strategy(migrator.migration.name)
            # Migrators are created according to discovered input for strategies, we do not expect NoneTypes here
            assert migration_input
            source_file = migration_input.config_path
            for transformation_result in migrator.results:
                source_path = transformation_result.spec.src_key
                target_path = transformation_result.spec.target_key
                # Skip None src_key as it represents full config, not a specific path
                if source_path is not None:
                    migration_mapping[source_path] = (source_file, target_path)

        # Show successfully migrated values with source and target mapping
        if migration_mapping:
            print_section("✅ ESS COMMUNITY VALUES CREATED SUCCESSFULLY :", logger=pretty_logger)
            # Prepare table data for migration mappings
            table_data = []
            for source_path, (source_file, target_path) in sorted(migration_mapping.items()):
                table_data.append([source_file, source_path, target_path])
            print_table(
                table_data,
                headers=["Source", "Path", "Target"],
                title="Migrated Values",
                logger=pretty_logger,
            )
            press_enter_to_continue(pretty_logger)

        if engine.ess_config["synapse"].get("workers"):
            print_section("📝 Discovered and enabled the following Synapse workers", logger=pretty_logger)
            # Prepare table data for workers
            worker_data = []
            for worker_type, worker_props in engine.ess_config["synapse"]["workers"].items():
                worker_data.append([worker_type, str(worker_props["replicas"])])
            print_table(
                worker_data,
                headers=["Worker", "Replicas"],
                title="Synapse Workers",
                logger=pretty_logger,
            )
            # ask user to take a second look
            pretty_logger.info("   ⚠️  Please review the workers in your values files before proceeding.\n")
        else:
            pretty_logger.info("   ✅ No workers found, using a single main Synapse process")
        if engine.discovered_secrets:
            press_enter_to_continue(pretty_logger)
            print_section("🔐 MIGRATED SECRETS:", logger=pretty_logger)
            # Prepare table data for secrets
            secret_data = []
            for discovered_secret in engine.discovered_secrets:
                secret_data.append(
                    [
                        discovered_secret.source_file,
                        discovered_secret.config_key,
                        discovered_secret.secret_key,
                    ]
                )
            print_table(
                secret_data,
                headers=["Source File", "Config Key", "Secret Path in Values"],
                title="Migrated Secrets",
                logger=pretty_logger,
            )

        if engine.init_by_ess_secrets:
            press_enter_to_continue(pretty_logger)
            print_section("⚠️  ESS-INITIALIZED SECRETS:", logger=pretty_logger)
            pretty_logger.info("The following Synapse secrets will be auto-generated by ESS:")
            # Prepare table data for auto-generated secrets
            init_secret_data = [[secret] for secret in engine.init_by_ess_secrets]
            print_table(
                init_secret_data,
                headers=["Secret Path in Values"],
                title="Auto-Generated Secrets",
                logger=pretty_logger,
            )
            pretty_logger.info(
                "These secrets are not required for migration but will be created automatically during deployment."
            )
            press_enter_to_continue(pretty_logger)

        # Show override warnings within the migration summary
        if engine.override_warnings:
            press_enter_to_continue(pretty_logger)
            print_section(
                "⚠️  ESS-MANAGED COMPONENTS CONFIGURATIONS DETECTED:",
                logger=pretty_logger,
            )
            pretty_logger.info(
                "   These components settings are managed by ESS Community and"
                " your settings may be overriden if they are not configurable in ESS:"
            )
            press_enter_to_continue(pretty_logger)

            # Prepare table data for override warnings
            override_data = [[warning] for warning in engine.override_warnings]
            print_table(
                override_data,
                headers=["Warning"],
                title="Override Warnings",
                logger=pretty_logger,
            )

            press_enter_to_continue(pretty_logger)
            print_section("❗ ACTION REQUIRED:", logger=pretty_logger)
            pretty_logger.info("   Remove these settings from your additional configuration to avoid conflicts.")
            pretty_logger.info("   They are now automatically managed by the ESS Helm chart.")
            press_enter_to_continue(pretty_logger)

        # Show underride warnings within the migration summary
        if engine.underride_warnings:
            press_enter_to_continue(pretty_logger)
            print_section(
                "ℹ️  DEVIATION FROM ESS COMMUNITY DEFAULT CONFIGURATIONS FOUND:",
                logger=pretty_logger,
            )
            pretty_logger.info("   These settings have ESS defaults that your values will override:")
            press_enter_to_continue(pretty_logger)

            # Prepare table data for underride warnings
            underride_data = [[warning] for warning in engine.underride_warnings]
            print_table(
                underride_data,
                headers=["Warning"],
                title="Underride Warnings",
                logger=pretty_logger,
            )

            press_enter_to_continue(pretty_logger)

        # Show clean migration message
        if not engine.override_warnings and not engine.underride_warnings:
            press_enter_to_continue(pretty_logger)
            print_section("🎉 CLEAN MIGRATION: No unexpected overrides detected!", logger=pretty_logger)
            pretty_logger.info("   All configurations have been properly migrated to ESS.")
            press_enter_to_continue(pretty_logger)

        # Show next steps for deployment
        print_section("🚀 NEXT STEPS TO DEPLOY ELEMENT SERVER SUITE:", logger=pretty_logger)
        press_enter_to_continue(pretty_logger)

        # Use incremental step numbering
        step_number = 1

        pretty_logger.info(f"{step_number}. Create Kubernetes namespace:")
        step_number += 1
        pretty_logger.info("   kubectl create namespace ess")

        # Check if there are configmaps or secrets to apply
        has_configmaps = len(configmap_paths) > 0
        has_secrets = len(secret_paths) > 0

        if has_configmaps or has_secrets:
            pretty_logger.info(f"{step_number}. Apply generated Kubernetes resources:")
            step_number += 1
            if has_configmaps:
                for configmap_path in configmap_paths:
                    pretty_logger.info(f"   kubectl apply -f {configmap_path} -n ess")
            if has_secrets:
                for secret_path in secret_paths:
                    pretty_logger.info(f"   kubectl apply -f {secret_path} -n ess")
            pretty_logger.info("")

        pretty_logger.info(f"{step_number}.Install ESS using Helm with the generated values:")
        step_number += 1
        pretty_logger.info(
            f'   helm upgrade --install --namespace "ess" ess '
            f"oci://ghcr.io/element-hq/ess-helm/matrix-stack -f {values_path} --wait"
        )
        press_enter_to_continue(pretty_logger)

        # Get the original media path from Synapse configuration
        synapse_input = engine.input_processor.input_for_strategy(SYNAPSE_STRATEGY_NAME)
        original_media_path = None
        if synapse_input and synapse_input.config.get("media_store_path"):
            original_media_path = synapse_input.config["media_store_path"]

        if original_media_path:
            pretty_logger.info(f"{step_number}. Copy media from your existing setup to ESS persistent volume:")
            pretty_logger.info(f"   kubectl cp {original_media_path} ess-synapse-0:/media/media_store -n ess")
            press_enter_to_continue(pretty_logger)

        pretty_logger.info("📚 For more details on deployment and data migration, refer to the ESS documentation.")
        press_enter_to_continue(pretty_logger)

        # Add database-specific instructions
        if not engine.global_options.use_existing_database:
            print_section("📋 DATABASE IMPORT INSTRUCTIONS", logger=pretty_logger)
            pretty_logger.info("Since you chose to use ESS-managed PostgreSQL, you'll need to import your")
            pretty_logger.info("existing database schema after deployment. Here are the steps:")
            press_enter_to_continue(pretty_logger)

            # Get source database configuration from input files
            synapse_input = engine.input_processor.input_for_strategy(SYNAPSE_STRATEGY_NAME)
            mas_input = engine.input_processor.input_for_strategy(MAS_STRATEGY_NAME)

            # Extract source database info from Synapse configuration
            assert synapse_input
            source_synapse_db = synapse_input.config["database"]["args"].get("dbname", "<source_synapse_db>")
            if not source_synapse_db:
                source_synapse_db = synapse_input.config["database"]["args"].get("database", "<source_synapse_db>")
            source_synapse_user = synapse_input.config["database"]["args"].get("user", "<source_synapse_user>")

            # Extract source database info from MAS configuration using existing helper
            if mas_input:
                mas_uri = mas_input.config["database"]["uri"]
                parsed_mas = parse_postgres_uri(mas_uri)
                source_mas_db = parsed_mas.get("name", "<source_mas_db>")
                source_mas_user = parsed_mas.get("user", "<source_mas_user>")

            # Get target database names and users from ESS configuration
            # These are the standard ESS target database names from the helm chart
            target_synapse_db = "synapse"
            target_synapse_user = "synapse_user"
            target_mas_db = "matrixauthenticationservice"
            target_mas_user = "matrixauthenticationservice_user"

            # Step 1: Stop workloads before importing
            step_number = 1
            pretty_logger.info(f"{step_number}. Stop Synapse and MAS workloads before importing:")
            pretty_logger.info(
                '   kubectl scale sts -l "app.kubernetes.io/component=matrix-server" -n ess --replicas=0'
            )
            if mas_input:
                pretty_logger.info(
                    '   kubectl scale deploy -l "app.kubernetes.io/component=matrix-authentication" -n ess --replicas=0'
                )
            press_enter_to_continue(pretty_logger)

            step_number += 1

            # Step 2: Create database dumps
            pretty_logger.info(f"{step_number}. After ESS is deployed, create database dumps for Synapse:")
            pretty_logger.info(f"   pg_dump -C -U {source_synapse_user} -d {source_synapse_db} > synapse.sql")

            # Only show MAS dump instructions if MAS is being migrated
            if mas_input:
                pretty_logger.info(f"   pg_dump -C -U {source_mas_user} -d {source_mas_db} > mas.sql")

            press_enter_to_continue(pretty_logger)
            step_number += 1

            # Step 3: Transform the dumps (only show if transformations are needed)
            synapse_needs_transform = (
                source_synapse_db != target_synapse_db or source_synapse_user != target_synapse_user
            )
            mas_needs_transform = mas_input and (source_mas_db != target_mas_db or source_mas_user != target_mas_user)

            if synapse_needs_transform or mas_needs_transform:
                pretty_logger.info(f"{step_number}. Transform the dumps to match ESS database names and owners:")

                # Only show database name transformation if source and target are different
                if source_synapse_db != target_synapse_db:
                    pretty_logger.info("   # Replace source database names with ESS database names")
                    pretty_logger.info(
                        f"   sed -i 's/DATABASE {source_synapse_db}/DATABASE {target_synapse_db}/' synapse.sql"
                    )

                # Only show MAS database transformation if MAS is being migrated and names are different
                if mas_input and source_mas_db != target_mas_db:
                    pretty_logger.info(f"   sed -i 's/DATABASE {source_mas_db}/DATABASE {target_mas_db}/' mas.sql")

                # Only show owner transformation if source and target are different
                if source_synapse_user != target_synapse_user:
                    pretty_logger.info("   # Replace source owners with ESS owners")
                    pretty_logger.info(
                        f"   sed -i 's/OWNER TO.*{source_synapse_user}/OWNER TO {target_synapse_user}/' synapse.sql"
                    )

                # Only show MAS owner transformation if MAS is being migrated and owners are different
                if mas_input and source_mas_user != target_mas_user:
                    pretty_logger.info(f"   sed -i 's/OWNER TO.*{source_mas_user}/OWNER TO {target_mas_user}/' mas.sql")

                press_enter_to_continue(pretty_logger)
                step_number += 1

            # Step: Copy the dumps
            pretty_logger.info(f"{step_number}. Copy the dumps to the ESS PostgreSQL pod:")
            pretty_logger.info("   kubectl cp synapse.sql ess-postgres-0:/tmp -n ess")

            # Only show MAS copy instructions if MAS is being migrated
            if mas_input:
                pretty_logger.info("   kubectl cp mas.sql ess-postgres-0:/tmp -n ess")

            press_enter_to_continue(pretty_logger)
            step_number += 1

            # Step: Import the dumps
            pretty_logger.info(f"{step_number}. Import the dumps into the ESS-managed PostgreSQL:")
            pretty_logger.info(
                '   kubectl exec -n ess sts/ess-postgres -- bash -c "psql -U postgres -d synapse < /tmp/synapse.sql"'
            )

            # Only show MAS import instructions if MAS is being migrated
            if mas_input:
                pretty_logger.info(
                    '   kubectl exec -n ess sts/ess-postgres -- bash -c "psql -U postgres -d '
                    'matrixauthenticationservice < /tmp/mas.sql"'
                )

            pretty_logger.info("")
            step_number += 1

            # Step: Restart workloads
            pretty_logger.info(f"{step_number}. Restart Synapse and MAS to use the imported data:")
            pretty_logger.info(
                '   kubectl scale sts -l "app.kubernetes.io/component=matrix-server" -n ess --replicas=1'
            )

            # Only show MAS restart instructions if MAS is being migrated
            if mas_input:
                pretty_logger.info(
                    '   kubectl scale deploy -l "app.kubernetes.io/component=matrix-authentication" -n ess --replicas=1'
                )

            press_enter_to_continue(pretty_logger)

        pretty_logger.info("=" * 60)

        reporter.report_success(args.output_dir)
        logging.info("Migration completed successfully!")
        logging.info(f"Output files written to: {args.output_dir}")
        return 0

    except ValidationError as e:
        reporter.report_failure(str(e))
        logging.error(f"Input validation failed: {e}")
        return 1
    except Exception as e:
        reporter.report_failure(str(e))
        logging.error(f"Migration failed: {e}")
        return 1
