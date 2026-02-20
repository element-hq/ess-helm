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
from .migration import MigrationStrategy, TransformationSpec
from .models import MigrationError, SecretConfig
from .utils import extract_hostname_from_url

logger = logging.getLogger("migration")

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
    pretty_logger: logging.Logger, instance_name: str, instance_props: Any, matched_worker_types: list[str]
) -> str:
    pretty_logger = logging.getLogger("migration:summary")

    if not matched_worker_types:
        matched_worker_types = worker_types

    logger.info("   No worker type found for instance %s (host: %s)", instance_name, instance_props["host"])
    pretty_logger.info(f"\n   ❌ No worker type found for instance {instance_name} (host: {instance_props['host']})")
    pretty_logger.info("   ❌ Available worker types")
    for i, worker_type in enumerate(matched_worker_types):
        pretty_logger.info(f"   ❌   {i + 1}. {worker_type}")

    while True:
        try:
            value = input(f"   Please select the worker type of instance {instance_name}: ").strip()
            if value:
                # make sure user selected an valid integer
                try:
                    worker_index = int(value) - 1
                    if worker_index in range(len(matched_worker_types)):
                        return matched_worker_types[worker_index]
                    else:
                        pretty_logger.info(f"Invalid worker type: {value}")
                except ValueError:
                    pretty_logger.info("   ❌ Please select a valid worker type.")
            else:
                pretty_logger.info("   ❌ Value cannot be empty. Please try again.")
        except KeyboardInterrupt as err:
            pretty_logger.info("\n   ❌ Operation cancelled by user")
            raise MigrationError("User cancelled worker input") from err
        except EOFError as err:
            pretty_logger.info("\n   ❌ End of input reached")
            raise MigrationError("End of input reached during worker prompt") from err


def extract_workers_from_instance_map(pretty_logger: logging.Logger, instance_map: dict[str, Any]) -> dict[str, Any]:
    """Extract workers from the instance map."""

    selected_workers = {}
    for instance_name in instance_map:
        matches = process.extract(instance_name, worker_types, scorer=fuzz.WRatio, limit=3)
        very_high_probable_matches = [m[0] for m in matches if m[1] > 90]
        matches = [m[0] for m in matches if m[1] > 60]
        selected_worker = (
            prompt_user_for_worker(pretty_logger, instance_name, instance_map[instance_name], matches)
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


@dataclass
class SynapseMigration(MigrationStrategy):
    """Synapse-specific migration implementation."""

    @property
    def component_root_key(self) -> str:
        return "synapse"

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
            "database.args.keepalives",
            "database.args.keepalives_idle",
            "database.args.keepalives_interval",
            "database.args.keepalives_count",
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
            "worker_replication_secret_path",
            "form_secret_path",
            "listeners",  # Listeners are also managed by ESS
        }

    @property
    def transformations(self) -> list[TransformationSpec]:
        return [
            TransformationSpec(src_key="server_name", target_key="serverName"),  # Required by default
            TransformationSpec(src_key="database.args.host", target_key="synapse.postgres.host"),  # Required by default
            TransformationSpec(
                src_key="database.args.port", target_key="synapse.postgres.port", required=False
            ),  # Optional - defaults to 5432
            TransformationSpec(src_key="database.args.user", target_key="synapse.postgres.user"),  # Required by default
            TransformationSpec(
                src_key="database.args.database", target_key="synapse.postgres.database"
            ),  # Required by default
            TransformationSpec(
                src_key="database.args.sslmode", target_key="synapse.postgres.sslMode", required=False
            ),  # Optional security feature
            TransformationSpec(
                src_key="public_baseurl",
                target_key="synapse.ingress.host",
                transformer=extract_hostname_from_url,
            ),  # Extract hostname from public_baseurl for ingress host
            TransformationSpec(
                src_key="instance_map",
                target_key="synapse.workers",
                transformer=extract_workers_from_instance_map,
                required=False,
            ),  # Extract workers from synapse instance_map
        ]

    @property
    def component_config_extras(self) -> dict[str, Any]:
        return {"enabled": True}


class SynapseSecretDiscovery(SecretDiscoveryStrategy):
    """Synapse-specific secret discovery implementation."""

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Get the ESS secret schema for Synapse."""
        return {
            # Synapse secrets
            "synapse.postgres.password": SecretConfig(
                init_if_missing_from_source_cfg=False,  # Must be provided
                description="Synapse database password",
                config_inline="database.args.password",
                config_path=None,
            ),
            "synapse.macaroon": SecretConfig(
                init_if_missing_from_source_cfg=False,  # This would break user tokens if changing after migrating
                description="Synapse macaroon secret",
                config_inline="macaroon_secret_key",
                config_path="macaroon_secret_key_path",
            ),
            "synapse.registrationSharedSecret": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Would break external scripts
                # if changing after migrating. Just warn about it, dont break.
                description="Registration shared secret",
                config_inline="registration_shared_secret",
                config_path="registration_shared_secret_path",
            ),
            "synapse.signingKey": SecretConfig(
                init_if_missing_from_source_cfg=False,  # This would break federation if changing after migrating
                description="Signing key",
                config_inline="signing_key",
                config_path="signing_key_path",
            ),
        }

    @property
    def component_name(self) -> str:
        return "Synapse"


class SynapseExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    @property
    def component_name(self) -> str:
        return "Synapse"

    @property
    def ignored_config_keys(self) -> list[str]:
        return [
            "media_store_path",  # Synapse media store path should be ignored
            "log_config",  # Log configuration is handled by the chart
        ]

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        ...
        return []
