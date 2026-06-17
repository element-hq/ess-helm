# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Main CLI entry point for the migration script.
"""

import argparse
import datetime
import logging

from .element_web import ELEMENT_WEB_STRATEGY_NAME
from .engine import MigrationEngine
from .hookshot import HOOKSHOT_STRATEGY_NAME
from .inputs import InputProcessor, ValidationError
from .mas import MAS_STRATEGY_NAME
from .models import GlobalOptions
from .outputs import create_output_dir, generate_helm_values, write_outputs
from .rich_output import ProgressReporter, log_command, print_prompt, print_section, print_separator, print_table
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

    # Validate and create output directory
    create_output_dir(args.output_dir)

    summary_fh = logging.FileHandler(
        f"{args.output_dir}/migration-summary-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    )
    summary_fh.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
        )
    )

    summary_logger = logging.getLogger("migration:summary")
    summary_logger.propagate = False
    summary_logger.setLevel(logging.INFO)
    summary_logger.addHandler(summary_fh)
    logger.addHandler(summary_fh)

    # Set up progress reporter
    steps = [
        LOADING_STEP,
        MIGRATING_STEP,
        GENERATING_VALUES_STEP,
        WRITING_OUTPUTS_STEP,
    ]
    global_options = GlobalOptions(
        quiet_mode=args.quiet,
    )
    reporter = ProgressReporter(
        summary_logger=summary_logger, steps=steps, verbose=args.verbose, global_options=global_options
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
        engine = MigrationEngine(
            input_processor=input_processor, summary_logger=summary_logger, global_options=global_options
        )

        # Set database mode if provided via command line
        if args.database_mode:
            if args.database_mode == "existing":
                engine.global_options.use_existing_database = True
            elif args.database_mode == "ess-managed":
                engine.global_options.use_existing_database = False
        else:
            # Prompt for database choice only if not already set via command line
            engine.global_options.use_existing_database = prompt_for_database_choice(
                summary_logger, global_options=engine.global_options
            )

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

        # Collect all written file paths for display
        all_file_paths = [values_path] + secret_paths + configmap_paths

        # Display migration summary
        press_enter_to_continue(summary_logger, engine.global_options)
        print_section("📊 MIGRATION SUMMARY", logger=summary_logger)

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
            # Prepare table data for migration mappings
            table_data = []
            for source_path, (source_file, target_path) in sorted(migration_mapping.items()):
                table_data.append([source_file, source_path, target_path])
            print_table(
                table_data,
                headers=["Source", "Path", "ESS Value"],
                title="✅ ESS COMMUNITY VALUES CREATED SUCCESSFULLY",
                logger=summary_logger,
            )
            press_enter_to_continue(summary_logger, engine.global_options)

        if engine.ess_config["synapse"].get("workers"):
            # Prepare table data for workers
            worker_data = []
            for worker_type, worker_props in engine.ess_config["synapse"]["workers"].items():
                worker_data.append([worker_type, str(worker_props["replicas"])])
            worker_data = sorted(worker_data, key=lambda w: w[0])
            print_table(
                worker_data,
                headers=["Worker", "Replicas"],
                title="📝 SYNAPSE WORKERS",
                logger=summary_logger,
            )
            # ask user to take a second look
            print_prompt(
                "   ⚠️  Please review the workers in your values files before proceeding.\n",
                style="default",
                logger=summary_logger,
            )
            press_enter_to_continue(summary_logger, engine.global_options)
        else:
            print_prompt(
                "   ✅ No workers found, using a single main Synapse process", style="default", logger=summary_logger
            )
            press_enter_to_continue(summary_logger, engine.global_options)
        if engine.discovered_secrets:
            # Prepare table data for secrets
            secret_data = []
            for discovered_secret in sorted(engine.discovered_secrets, key=lambda ds: ds.source_file + ds.config_key):
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
                title="🔐 MIGRATED SECRETS",
                logger=summary_logger,
            )
            press_enter_to_continue(summary_logger, engine.global_options)

        if engine.init_by_ess_secrets:
            # Prepare table data for auto-generated secrets
            init_secret_data = sorted([[secret] for secret in engine.init_by_ess_secrets], key=lambda ds: ds[0])
            print_table(
                init_secret_data,
                headers=["Secret Path in Values"],
                title="ℹ️  ESS-INITIALIZED SECRETS",
                logger=summary_logger,
            )
            summary_logger.info(
                "These secrets are not required for migration but will be created automatically during deployment."
            )
            press_enter_to_continue(summary_logger, engine.global_options)

        # Show override warnings within the migration summary
        if engine.override_warnings:
            # Prepare table data for override warnings
            override_data = [[warning] for warning in engine.override_warnings]
            print_table(
                override_data,
                headers=["Warning"],
                title="⚠️  ESS-MANAGED COMPONENTS CONFIGURATIONS DETECTED",
                logger=summary_logger,
            )
            summary_logger.info(
                "   These components settings are managed by ESS Community and"
                " your settings may be overriden if they are not configurable in ESS"
            )
            press_enter_to_continue(summary_logger, engine.global_options)

            print_section(
                "❗ ACTION REQUIRED:\n   "
                "Double-check and maybe remove these settings from your additional configuration to avoid conflicts.",
                logger=summary_logger,
            )

            press_enter_to_continue(summary_logger, engine.global_options)

        # Show underride warnings within the migration summary
        if engine.underride_warnings:
            # Prepare table data for underride warnings
            underride_data = [[warning] for warning in engine.underride_warnings]
            print_table(
                underride_data,
                headers=["Warning"],
                title="ℹ️  DEVIATION FROM ESS COMMUNITY DEFAULT CONFIGURATIONS FOUND",
                logger=summary_logger,
            )

            print_prompt(
                "   These settings have ESS defaults that your values will override",
                style="default",
                logger=summary_logger,
            )
            press_enter_to_continue(summary_logger, engine.global_options)

        # Show clean migration message
        if not engine.override_warnings and not engine.underride_warnings:
            press_enter_to_continue(summary_logger, engine.global_options)
            print_section("🎉 CLEAN MIGRATION: No unexpected overrides detected!", logger=summary_logger)
            print_prompt(
                "   All configurations have been properly migrated to ESS.", style="default", logger=summary_logger
            )
            press_enter_to_continue(summary_logger, engine.global_options)

        # Show next steps for deployment
        print_section("🚀 NEXT STEPS TO DEPLOY ELEMENT SERVER SUITE:", logger=summary_logger)
        press_enter_to_continue(summary_logger, engine.global_options)

        # Use incremental step numbering
        step_number = 1

        print_prompt(f"{step_number}. Create Kubernetes namespace:", style="default", logger=summary_logger)
        step_number += 1
        log_command("kubectl create namespace ess", logger=summary_logger)

        # Check if there are configmaps or secrets to apply
        has_configmaps = len(configmap_paths) > 0
        has_secrets = len(secret_paths) > 0

        if has_configmaps or has_secrets:
            print_prompt(
                f"{step_number}. Apply generated Kubernetes resources:", style="default", logger=summary_logger
            )
            step_number += 1
            if has_configmaps:
                for configmap_path in configmap_paths:
                    log_command(f"kubectl apply -f {configmap_path} -n ess", logger=summary_logger)
            if has_secrets:
                for secret_path in secret_paths:
                    log_command(f"kubectl apply -f {secret_path} -n ess", logger=summary_logger)
            print_prompt("", style="default", logger=summary_logger)

        print_prompt(
            f"{step_number}.Install ESS using Helm with the generated values:", style="default", logger=summary_logger
        )
        step_number += 1
        log_command(
            f'helm upgrade --install --namespace "ess" ess '
            f"oci://ghcr.io/element-hq/ess-helm/matrix-stack -f {values_path} --wait",
            logger=summary_logger,
        )
        press_enter_to_continue(summary_logger, engine.global_options)

        engine.manual_procedure(step_number)

        print_separator(logger=summary_logger)

        reporter.report_success(args.output_dir, all_file_paths)
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
