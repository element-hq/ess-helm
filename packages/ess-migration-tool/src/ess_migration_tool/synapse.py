# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Synapse-specific migration strategy.
"""

import logging
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

from .interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec, additional_config_transformer
from .models import DiscoverableSecret, DiscoveredSecret, GlobalOptions, MigrationError, SecretConfig
from .rich_output import print_prompt
from .utils import (
    extract_hostname_from_url,
    get_nested_value,
    prompt_choice,
    prompt_value,
    yaml_dump_with_pipe_for_multiline,
)

logger = logging.getLogger("migration")

SYNAPSE_STRATEGY_NAME = "Synapse"
SYNAPSE_COMPONENT_ROOT_KEY = "synapse"

worker_types = [
    "main",
    "account-data",
    "appservice",
    "background",
    "client-reader",
    "device-lists",
    "encryption",
    "event-creator",
    "event-persister",
    "federation-inbound",
    "federation-reader",
    "federation-sender",
    "initial-synchrotron",
    "media-repository",
    "presence-writer",
    "push-rules",
    "pusher",
    "receipts",
    "sliding-sync",
    "sso-login",
    "synchrotron",
    "typing-persister",
    "user-dir",
]


def prompt_user_for_worker(
    config_value_transformer: ConfigValueTransformer,
    instance_name: str,
    instance_props: Any,
    matched_worker_types: list[str],
    global_options: GlobalOptions,
) -> str:
    if not matched_worker_types:
        matched_worker_types = worker_types

    logger.info("   No worker type found for instance %s (host: %s)", instance_name, instance_props["host"])
    config_value_transformer.summary_logger.info(
        f"   ❌ No worker type found for instance {instance_name} (host: {instance_props['host']})"
    )
    print_prompt("   ❌ Available worker types", style="default", logger=config_value_transformer.summary_logger)
    for i, worker_type in enumerate(matched_worker_types):
        print_prompt(f"   ❌   {i + 1}. {worker_type}", style="default", logger=config_value_transformer.summary_logger)

    selected_worker = prompt_choice(
        config_value_transformer.summary_logger,
        f"Please select the worker type of instance {instance_name}:",
        matched_worker_types,
        global_options,
    )
    return selected_worker


def extract_workers_from_instance_map(
    config_value_transformer: ConfigValueTransformer, instance_map: dict[str, Any] | None, **kwargs: Any
) -> dict[str, Any] | None:
    """Extract workers from the instance map."""

    selected_workers = {}
    if instance_map is None:
        return None

    for instance_name in instance_map:
        matches = process.extract(instance_name, worker_types, scorer=fuzz.WRatio, limit=3)
        very_high_probable_matches = [m[0] for m in matches if m[1] > 90]
        probable_matches = [m[0] for m in matches if m[1] > 60]
        selected_worker = (
            prompt_user_for_worker(
                config_value_transformer,
                instance_name,
                instance_map[instance_name],
                probable_matches,
                kwargs["global_options"],
            )
            if len(very_high_probable_matches) != 1
            else very_high_probable_matches[0]
        )
        if selected_worker == "main":
            continue
        if selected_worker not in selected_workers:
            selected_workers[selected_worker] = {
                "enabled": True,
                "replicas": 1,
            }
        else:
            selected_workers[selected_worker]["replicas"] += 1
    return selected_workers


def extract_database_name(
    config_value_transformer: ConfigValueTransformer, database_args: dict[str, Any], **kwargs: Any
) -> str:
    """Extract database name from the database arguments."""
    database_name = database_args.get("dbname")
    if not database_name:
        database_name = database_args.get("database")
    if not database_name:
        print_prompt(
            "   ❌ Synapse database name could not be found",
            style="default",
            logger=config_value_transformer.summary_logger,
        )
        raise MigrationError("No synapse database name found")
    return database_name


def prompt_for_ingress_host(
    config_value_transformer: ConfigValueTransformer, public_baseurl: str | None, **kwargs: Any
) -> str:
    """
    Prompt user for ingress host when public_baseurl is missing.

    Args:
        config_value_transformer: ConfigValueTransformer instance
        public_baseurl: The public base URL from source config (may be None or empty)
        **kwargs: Optional context parameters (unused)

    Returns:
        The ingress host (hostname extracted from public_baseurl or user input)

    Raises:
        MigrationError: If user cancels the operation
    """
    # If public_baseurl is provided, extract hostname from it (existing behavior)
    if public_baseurl:
        return extract_hostname_from_url(config_value_transformer, public_baseurl)

    # If public_baseurl is missing, prompt user for ingress host directly
    print_prompt(
        "\n   ❌ Synapse public_baseurl not found in configuration",
        style="default",
        logger=config_value_transformer.summary_logger,
    )
    print_prompt(
        "   ❌ The chart requires Synapse Public BaseURL to be distinct from the server name",
        style="default",
        logger=config_value_transformer.summary_logger,
    )
    print_prompt(
        "   ❌ Please provide Synapse ingress host (e.g., matrix.example.com):",
        style="default",
        logger=config_value_transformer.summary_logger,
    )

    return prompt_value(
        config_value_transformer.summary_logger,
        "Enter ingress host:",
        kwargs["global_options"],
    )


def filter_listeners(_, listeners: list[dict] | None, **kwargs: Any) -> dict[str, Any] | None:
    """
    Filter out listeners that are managed by the ESS chart.

    The chart manages listeners that serve specific resources: client, federation, replication, metrics, health.
    This function removes listeners that serve only ESS-managed resources and keeps custom listeners,
    returning them as a dictionary structure for additional config.

    Args:
        listeners: List of listener configurations from source Synapse config
        **kwargs: Optional context parameters (unused)

    Returns:
        Dictionary with listeners.yml config structure, or None if no custom listeners remain
    """
    if not listeners:
        return None

    # Resources managed by the ESS chart that should be filtered out
    chart_managed_resources = {"client", "federation", "replication", "metrics"}

    # Ports managed by the ESS chart that should be filtered out
    chart_managed_ports = {8008, 8080, 8448, 9093, 9001}

    filtered_listeners = []
    for listener in listeners:
        # Get the listener port
        listener_port = listener.get("port")

        # Check if this listener uses a chart-managed port
        uses_managed_port = listener_port in chart_managed_ports

        # Filter out listeners that use chart-managed ports
        if uses_managed_port:
            logger.debug("Filtered out listener using managed port: %s", listener_port)
            continue

        # Filter resources: keep only non-chart-managed resources
        filtered_resources = []
        original_resources = listener.get("resources", [])

        for resource in original_resources:
            names = resource.get("names", [])
            name_set = set(names) if isinstance(names, list) else {names}

            # Remove chart-managed resources, keep only custom ones
            unmanaged_names = name_set - chart_managed_resources
            if unmanaged_names:
                new_resource = resource.copy()
                new_resource["names"] = list(unmanaged_names)
                filtered_resources.append(new_resource)

        # Keep listener only if it has any custom resources left
        if filtered_resources:
            new_listener = listener.copy()
            new_listener["resources"] = filtered_resources
            filtered_listeners.append(new_listener)
            logger.debug(
                f"Importing listener port {listener_port} with filtered resources:"
                f"{','.join(*[r['names'] for r in filtered_resources])}"
            )
        else:
            logger.debug(f"Filtered out listener port {listener_port} with only chart-managed resources")

    if not filtered_listeners:
        return None

    # Return the structure for additional config
    return {"listeners.yml": {"config": yaml_dump_with_pipe_for_multiline({"listeners": filtered_listeners})}}


@dataclass
class SynapseMigration(MigrationStrategy):
    """Synapse-specific migration implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def name(self) -> str:
        return SYNAPSE_STRATEGY_NAME

    @property
    def override_configs(self) -> set[str]:
        return {
            "public_baseurl",
            "server_name",
            "database.args.host",
            "database.args.port",
            "database.args.user",
            "database.args.password",
            "database.args.database",
            "database.args.sslmode",
            "database.args.application_name",
            "ip_range_blacklist",
            "signing_key_path",
            "start_pushers",
            "pusher_instances",
            "update_user_directory_from_worker",
            "instance_map",
            "instance_map.main",
            "instance_map.host",
            "instance_map.port",
            "redis",
            "redis.enabled",
            "redis.host",
            "stream_writers",
            "enable_metrics",
            "log_config",
            "macaroon_secret_key_path",
            "registration_shared_secret_path",
            "listeners",  # Listeners are also managed by ESS
            "app_service_config_files",  # In theory we can use extra file for this
            # In practice, the migration-tool manages it using ESS high level values
            "notify_appservices_from_worker",
            "run_background_tasks_on",
            "send_federation",
            "federation_sender_instances",
            "max_upload_size",
            "media_instance_running_background_jobs",
            "push_instances",
            "worker_app",
            "media_store_path",
            "enable_media_repo",
        }

    @property
    def underride_configs(self) -> set[str]:
        """Config keys that are ESS defaults (users can override these via additional config)."""
        return {
            "web_client_location",
            "report_stats",
            "require_auth_for_profile_requests",
            "federation_client_minimum_tls_version",
            "experimental_features.msc4028_push_encrypted_events",
            "url_preview_enabled",
            "url_preview_ip_range_whitelist",
            "url_preview_ip_range_blacklist",
            "database.args.keepalives",
            "database.args.keepalives_idle",
            "database.args.keepalives_interval",
            "database.args.keepalives_count",
            "database.args.cp_min",
            "database.args.cp_max",
            "database.args.sslrootcert",
            "max_event_delay_duration",
            "rc_message.per_second",
            "rc_message.burst_count",
            "rc_delayed_event_mgmt.per_second",
            "rc_delayed_event_mgmt.burst_count",
        }

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get transformations based on database choice."""

        # Lambda to wrap additional_config_transformer with Synapse-specific context
        def synapse_additional_transformer(
            config_value_transformer: "ConfigValueTransformer",
            value: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return additional_config_transformer(
                config_value_transformer,
                value,
                component_root_key=SYNAPSE_COMPONENT_ROOT_KEY,
                override_configs=self.override_configs,
                underride_configs=self.underride_configs,
                component_name=SYNAPSE_STRATEGY_NAME,
                **kwargs,
            )

        base_transformations = [
            # Enable Synapse component
            TransformationSpec(
                src_key=None,
                target_key="synapse.enabled",
                transformer=lambda *_, **__: True,
            ),
            TransformationSpec(src_key="server_name", target_key="serverName"),
            TransformationSpec(
                src_key="public_baseurl",
                target_key="synapse.ingress.host",
                transformer=prompt_for_ingress_host,
            ),  # Prompt for ingress host if public_baseurl is missing
            TransformationSpec(
                src_key="web_client_location",
                target_key="elementWeb.ingress.host",
                transformer=lambda _, url, **kw: extract_hostname_from_url(_, url, **kw) if url else None,
                required=False,
            ),  # Extract Element Web ingress host from web_client_location
            TransformationSpec(
                src_key="instance_map",
                target_key="synapse.workers",
                transformer=extract_workers_from_instance_map,
                required=False,
            ),  # Extract workers from synapse instance_map
            TransformationSpec(
                src_key="listeners",
                target_key="synapse.additional",
                transformer=filter_listeners,
                required=False,
            ),  # Filter out chart-managed listeners and output to additional config
            TransformationSpec(
                src_key="matrix_authentication_service",
                target_key="matrixAuthenticationService.enabled",
                transformer=lambda _, mas, **__: mas.get("enabled") if mas else None,
                required=False,
            ),
            TransformationSpec(
                src_key="max_upload_size",
                target_key="synapse.media.maxUploadSize",
                required=False,
            ),
            # ... other non-database transformations ...
        ]

        if self.global_options.use_existing_database:
            # External database: import all database configuration
            transformations = base_transformations + [
                TransformationSpec(src_key="database.args.host", target_key="synapse.postgres.host"),
                TransformationSpec(src_key="database.args.port", target_key="synapse.postgres.port", required=False),
                TransformationSpec(src_key="database.args.user", target_key="synapse.postgres.user"),
                TransformationSpec(
                    src_key="database.args", target_key="synapse.postgres.database", transformer=extract_database_name
                ),
                TransformationSpec(
                    src_key="database.args.sslmode", target_key="synapse.postgres.sslMode", required=False
                ),  # Optional security feature
                # ... other database property transformations ...
                # Generic additional config generation must be last to capture all tracked sources
            ]
        else:
            # ESS-managed: set postgres.enabled flag
            transformations = base_transformations + [
                TransformationSpec(
                    src_key="database",  # Trigger on database section
                    target_key="postgres.enabled",
                    transformer=lambda _, __, **kw: True,  # Set to True for ESS-managed PostgreSQL
                ),
            ]
        # Generic additional config generation must be last to capture all tracked sources
        return transformations + [
            TransformationSpec(
                src_key=None,
                target_key="synapse.additional",
                transformer=synapse_additional_transformer,
                required=False,
            ),
        ]


class SynapseSecretDiscovery(SecretDiscoveryStrategy):
    """Synapse-specific secret discovery implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def name(self) -> str:
        return SYNAPSE_STRATEGY_NAME

    @property
    def ess_secret_schema(self) -> dict[str, DiscoverableSecret]:
        """Get the ESS secret schema for Synapse."""
        schema: dict[str, DiscoverableSecret] = {
            # Synapse secrets
            "synapse.appservices.*": DiscoverableSecret(
                description="Appservice registration files",
                init_if_missing_from_source_cfg=False,
                optional=True,
            ),
        }

        # Only include PostgreSQL password when using existing database
        if self.global_options.use_existing_database:
            schema["synapse.postgres.password"] = DiscoverableSecret(
                description="Synapse database password",
                init_if_missing_from_source_cfg=False,  # Must be provided
                discovery=SecretConfig(
                    config_inline="database.args.password",
                    config_path=None,
                ),
            )

        # Other Synapse secrets (always included)
        schema.update(
            {
                "synapse.macaroon": DiscoverableSecret(
                    description="Synapse macaroon secret",
                    init_if_missing_from_source_cfg=False,  # This would break user tokens if changing after migrating
                    discovery=SecretConfig(
                        config_inline="macaroon_secret_key",
                        config_path="macaroon_secret_key_path",
                    ),
                ),
                "synapse.registrationSharedSecret": DiscoverableSecret(
                    description="Registration shared secret",
                    init_if_missing_from_source_cfg=True,  # Would break external scripts
                    # if changing after migrating. Just warn about it, dont break.
                    discovery=SecretConfig(
                        config_inline="registration_shared_secret",
                        config_path="registration_shared_secret_path",
                    ),
                ),
                "synapse.signingKey": DiscoverableSecret(
                    description="Signing key",
                    init_if_missing_from_source_cfg=False,  # This would break federation if changing after migrating
                    discovery=SecretConfig(
                        config_inline="signing_key",
                        config_path="signing_key_path",
                    ),
                ),
                "matrixAuthenticationService.synapseSharedSecret": DiscoverableSecret(
                    description="Synapse-MAS shared secret",
                    init_if_missing_from_source_cfg=True,  # Can be auto-generated
                    discovery=SecretConfig(
                        config_inline="matrix_authentication_service.secret",
                        config_path="matrix_authentication_service.secret_path",
                    ),
                ),
            }
        )

        return schema

    @property
    def secret_name(self) -> str:
        return "synapse"

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Discover component-specific secrets from configuration.

        Discovers appservice registration files from the app_service_config_files configuration.

        Args:
            source_file: Source configuration file name
            config_data: Synapse configuration data

        Returns:
            Tuple of (discovered_secrets, failed_secrets) where:
            - discovered_secrets: Dictionary mapping ESS secret keys to DiscoveredSecret objects
            - failed_secrets: List of (DiscoveredSecret, error_message) tuples for secrets
              that were discovered but could not be read
        """
        discovered: dict[str, DiscoveredSecret] = {}
        failed: list[tuple[DiscoveredSecret, str]] = []

        # Get app_service_config_files from config (always a list)
        file_paths = get_nested_value(config_data, "app_service_config_files")
        if not file_paths or not isinstance(file_paths, list):
            return discovered, failed

        # Read each file and create discovered secrets
        for idx, file_path in enumerate(file_paths):
            secret_key = f"synapse.appservices.{idx}"
            config_key = f"app_service_config_files.{idx}"

            try:
                with open(file_path) as f:
                    file_content = f.read()
                discovered[secret_key] = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=secret_key,
                    config_key=config_key,
                    value=file_content,
                )
            except Exception as e:
                failed_secret = DiscoveredSecret(
                    source_file=source_file,
                    secret_key=secret_key,
                    config_key=config_key,
                    value="",
                )
                failed.append((failed_secret, f"Failed to read file {file_path}: {e}"))

        return discovered, failed


class SynapseExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    @property
    def component_name(self) -> str:
        return SYNAPSE_STRATEGY_NAME

    @property
    def component_root_key(self) -> str:
        return SYNAPSE_COMPONENT_ROOT_KEY

    @property
    def ignored_config_keys(self) -> list[str]:
        return [
            "media_store_path",  # Synapse media store path should be ignored
            "log_config",  # Log configuration is handled by the chart
            "pid_file",  # We do not care of importing pid files
        ]

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        ...
        return []
