# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Synapse-specific migration strategy.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .migration import MigrationStrategy, TransformationSpec
from .models import SecretConfig
from .secrets import SecretDiscoveryStrategy
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


class SynapseSecretDiscovery(SecretDiscoveryStrategy):
    """Synapse-specific secret discovery implementation."""

    @property
    def ess_secret_schema(self) -> dict[str, Callable[[dict[str, Any]], SecretConfig]]:
        """Get the ESS secret schema for Synapse."""
        return {
            # Synapse secrets
            "synapse.postgres.password": lambda _: SecretConfig(
                init_if_missing_from_source_cfg=False,  # Must be provided
                description="Synapse database password",
                config_inline="database.args.password",
                config_path=None,
            ),
            "synapse.macaroon": lambda _: SecretConfig(
                init_if_missing_from_source_cfg=False,  # This would break user tokens if changing after migrating
                description="Synapse macaroon secret",
                config_inline="macaroon_secret_key",
                config_path="macaroon_secret_key_path",
            ),
            "synapse.registrationSharedSecret": lambda _: SecretConfig(
                init_if_missing_from_source_cfg=True,  # Would break external scripts
                # if changing after migrating. Just warn about it, dont break.
                description="Registration shared secret",
                config_inline="registration_shared_secret",
                config_path="registration_shared_secret_path",
            ),
            "synapse.signingKey": lambda _: SecretConfig(
                init_if_missing_from_source_cfg=False,  # This would break federation if changing after migrating
                description="Signing key",
                config_inline="signing_key",
                config_path="signing_key_path",
            ),
        }

    @property
    def component_name(self) -> str:
        return "Synapse"
