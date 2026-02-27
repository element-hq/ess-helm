# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Main CLI entry point for the migration script.
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field

from .engine import MigrationEngine
from .inputs import InputProcessor, ValidationError
from .models import MigrationError
from .outputs import generate_helm_values, write_outputs

LOADING_STEP = "Loading and validating input files"
MIGRATING_STEP = "Migrating configuration to ESS values"
GENERATING_VALUES_STEP = "Generating Helm values"
WRITING_OUTPUTS_STEP = "Writing output files"

logger = logging.getLogger("migration")


@dataclass
class ProgressReporter:
    """Handles progress reporting for the migration process."""

    pretty_logger: logging.Logger
    verbose: bool = field(default=False)
    current_step: int = field(default=-1)
    all_steps: list[str] = field(default_factory=list)

    def __post_init__(self):
        # List of steps and the order we expect to report
        self.all_steps = [
            LOADING_STEP,
            MIGRATING_STEP,
            GENERATING_VALUES_STEP,
            WRITING_OUTPUTS_STEP,
        ]

    def start_migration(self):
        """Report migration start."""
        self.pretty_logger.info("🚀 Starting Matrix Stack to ESS Migration")

    def report_step(self, step_name: str):
        """Report progress on a specific step."""
        if step_name != self.all_steps[self.current_step + 1]:
            raise MigrationError("Migration engine tried to run an unexpected step")

        self.current_step += 1
        progress = self.current_step / len(self.all_steps) * 100
        self.pretty_logger.info(f"📦 Step {self.current_step}/{len(self.all_steps)} ({progress:.0f}%): {step_name}")

    def report_success(self, output_dir: str):
        """Report successful completion."""
        self.pretty_logger.info("✅ Migration completed successfully!")
        self.pretty_logger.info(f"📁 Output files written to: {output_dir}")
        self.pretty_logger.info("🎉 Ready to deploy with Element Server Suite!")

    def report_failure(self, error: str):
        """Report migration failure."""
        self.pretty_logger.info("❌ Migration failed!")
        self.pretty_logger.info(f"💥 Error: {error}")
        self.pretty_logger.info("📚 Check logs for details and try again.")


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
    pretty_sh.setFormatter(
        logging.Formatter(
            "%(message)s",
        )
    )
    pretty_logger.addHandler(pretty_sh)

    # Set up progress reporter
    reporter = ProgressReporter(pretty_logger=pretty_logger)

    try:
        reporter.start_migration()

        # Load migration input
        reporter.report_step(LOADING_STEP)
        input_processor = InputProcessor()
        input_processor.load_migration_input(
            name="synapse",
            config_path=args.synapse_config,
        )

        # Run migration
        reporter.report_step(MIGRATING_STEP)
        engine = MigrationEngine(input_processor=input_processor, pretty_logger=pretty_logger)
        ess_values = engine.run_migration()

        # Generate outputs
        reporter.report_step(GENERATING_VALUES_STEP)
        helm_values = generate_helm_values(ess_values)

        # Write outputs
        reporter.report_step(WRITING_OUTPUTS_STEP)
        write_outputs(
            helm_values=helm_values,
            secrets=engine.secrets,
            configmaps=engine.configmaps,
            output_dir=args.output_dir,
        )

        # Display migration summary
        pretty_logger.info("\n📊 MIGRATION SUMMARY")
        pretty_logger.info("=" * 60)

        # Create a comprehensive mapping of source config paths to target ESS paths
        migration_mapping = {}

        # Process migrations
        for migrator in engine.migrators:
            source_file = engine.input_processor.input_for_component(migrator.component_root_key).config_path
            for transformation_result in migrator.config_to_ess_transformer.results:
                source_path = transformation_result.spec.src_key
                target_path = transformation_result.spec.target_key
                migration_mapping[source_path] = (source_file, target_path)

        # Show successfully migrated values with source and target mapping
        if migration_mapping:
            pretty_logger.info("✅ SUCCESSFULLY MIGRATED TO ESS:")
            for source_path, (source_file, target_path) in sorted(migration_mapping.items()):
                pretty_logger.info(f"   • {source_file}: {source_path} → {target_path}")
            pretty_logger.info("")

        if engine.ess_config["synapse"].get("workers"):
            pretty_logger.info("📝 Discovered and enabled the following Synapse workers")
            for worker_type, worker_props in engine.ess_config["synapse"]["workers"].items():
                pretty_logger.info(f"   -   {worker_type} (replicas: {worker_props['replicas']})")
            # ask user to take a second look
            pretty_logger.info("   ⚠️  Please review the workers in your values files before proceeding.\n")
        else:
            pretty_logger.info("   ✅ No workers found, using a single main Synapse process")
        if engine.discovered_secrets:
            pretty_logger.info("🔐 MIGRATED SECRETS:")
            for discovered_secret in engine.discovered_secrets:
                pretty_logger.info(
                    f"   • {discovered_secret.source_file}: {discovered_secret.config_key} → "
                    f"{discovered_secret.secret_key}"
                )

        if engine.init_by_ess_secrets:
            pretty_logger.info("\n⚠️  ESS-INITIALIZED SECRETS:")
            pretty_logger.info("The following Synapse secrets will be auto-generated by ESS:")
            for secret in engine.init_by_ess_secrets:
                pretty_logger.info(f"   • {secret}")
            pretty_logger.info(
                "These secrets are not required for migration but will be created automatically during deployment."
            )

        # Show override warnings within the migration summary
        if engine.override_warnings:
            pretty_logger.info("\n⚠️  ESS-MANAGED CONFIGURATIONS FOUND:")
            pretty_logger.info("   These settings are managed by ESS and will be overridden:")
            pretty_logger.info("")

            for warning in engine.override_warnings:
                pretty_logger.info(f"   • {warning}")

            pretty_logger.info("")
            pretty_logger.info("❗ ACTION REQUIRED:")
            pretty_logger.info("   Remove these settings from your additional configuration to avoid conflicts.")
            pretty_logger.info("   They are now automatically managed by the ESS Helm chart.")
            pretty_logger.info("")

        # Show clean migration message
        if not engine.override_warnings:
            pretty_logger.info("🎉 CLEAN MIGRATION: No unexpected overrides detected!")
            pretty_logger.info("   All configurations have been properly migrated to ESS.")
            pretty_logger.info("")

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


if __name__ == "__main__":
    # Run the main function
    exit_code = main()
    sys.exit(exit_code)
