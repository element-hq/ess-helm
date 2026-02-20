# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Synapse-specific migration strategy.
"""

from dataclasses import dataclass
from typing import Any

from .migration import MigrationStrategy, TransformationSpec
from .utils import extract_hostname_from_url


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
        ]

    @property
    def component_config_extras(self) -> dict[str, Any]:
        return {"enabled": True}
