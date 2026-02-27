# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Synapse-specific migration strategy.
"""

import logging
import urllib
from dataclasses import dataclass
from typing import Any

from .migration import MigrationStrategy, TransformationSpec
from .models import SecretConfig
from .secrets import SecretDiscoveryStrategy
from .utils import extract_hostname_from_url

logger = logging.getLogger("migration")


def parse_postgres_uri(uri: str) -> dict[str, Any]:
    """
    Parse a PostgreSQL connection URI and extract database configuration.

    Args:
        uri: PostgreSQL connection URI (e.g., "postgresql://user:pass@host:port/db?sslmode=prefer")

    Returns:
        Dictionary with database configuration fields (port is returned as int)
    """
    if not uri or not uri.startswith("postgresql://"):
        return {}

    try:
        # Parse the URI
        parsed = urllib.parse.urlparse(uri)

        # Build result dictionary only with fields that are actually present
        result: dict[str, str | int | None] = {}

        if parsed.hostname:
            result["host"] = parsed.hostname

        if parsed.port:
            result["port"] = int(parsed.port)

        if parsed.username:
            result["user"] = parsed.username

        if parsed.password:
            result["password"] = parsed.password

        if parsed.path:
            result["name"] = parsed.path.lstrip("/")

        # Extract SSL mode from query parameters (only if present)
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            if "sslmode" in query_params:
                result["ssl"] = query_params["sslmode"][0]

        return result
    except Exception as e:
        logging.warning(f"Failed to parse PostgreSQL URI '{uri}': {e}")
        return {}


def extract_port_from_uri(uri: str) -> int | None:
    """
    Extract port from PostgreSQL URI, returning None if not present.

    Args:
        uri: PostgreSQL connection URI

    Returns:
        Port as integer if present, None otherwise
    """
    parsed = parse_postgres_uri(uri)
    port = parsed.get("port")
    return int(port) if port is not None else None


@dataclass
class MASMigration(MigrationStrategy):
    """MAS-specific migration implementation."""

    @property
    def component_root_key(self) -> str:
        return "matrixAuthenticationService"

    @property
    def override_configs(self) -> set[str]:
        return {
            "http",  # The entire HTTP configuration is managed by ESS
            "database.uri",  # Database URI configuration is managed by ESS
            "encryption",  # Encryption settings are managed by ESS
            "token",  # Token configuration is managed by ESS
        }

    @property
    def transformations(self) -> list[TransformationSpec]:
        return [
            TransformationSpec(
                src_key="database.uri",
                target_key="matrixAuthenticationService.postgres.host",
                transformer=lambda uri: parse_postgres_uri(uri).get("host"),
                required=True,
            ),
            TransformationSpec(
                src_key="database.uri",
                target_key="matrixAuthenticationService.postgres.port",
                transformer=extract_port_from_uri,
                required=False,
            ),
            TransformationSpec(
                src_key="database.uri",
                target_key="matrixAuthenticationService.postgres.user",
                transformer=lambda uri: parse_postgres_uri(uri).get("user"),
                required=True,
            ),
            TransformationSpec(
                src_key="database.uri",
                target_key="matrixAuthenticationService.postgres.database",
                transformer=lambda uri: parse_postgres_uri(uri).get("name"),
                required=True,
            ),
            TransformationSpec(
                src_key="database.uri",
                target_key="matrixAuthenticationService.postgres.sslMode",
                transformer=lambda uri: parse_postgres_uri(uri).get("ssl"),
                required=False,
            ),
            TransformationSpec(
                src_key="http.public_base",
                target_key="matrixAuthenticationService.ingress.host",
                transformer=extract_hostname_from_url,
            ),  # Extract hostname from http.public_base for ingress host
        ]


class MASSecretDiscovery(SecretDiscoveryStrategy):
    """MAS-specific secret discovery implementation."""

    @property
    def component_name(self) -> str:
        return "Matrix Authentication Service"

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Get the ESS secret schema for MAS."""
        return {
            # MAS secrets
            "matrixAuthenticationService.postgres.password": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Must be provided
                description="MAS database password",
                config_inline="database.uri",
                config_path=None,
                transformer=lambda uri: parse_postgres_uri(uri).get("password"),
            ),
            "matrixAuthenticationService.synapseSharedSecret": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Can be auto-generated
                description="MAS Synapse shared secret",
                config_inline="matrix.secret",
                config_path="matrix.secret_file",
            ),
            "matrixAuthenticationService.encryptionSecret": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Must be provided
                description="MAS encryption secret",
                config_inline="secrets.encryption",
                config_path="secrets.encryption_file",
            ),
            "matrixAuthenticationService.privateKeys.rsa": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Can be auto-generated
                description="MAS RSA private key",
                config_inline="",
                config_path="",
            ),
            "matrixAuthenticationService.privateKeys.ecdsaPrime256v1": SecretConfig(
                init_if_missing_from_source_cfg=True,  # Can be auto-generated
                description="MAS ECDSA private key",
                config_inline="",
                config_path="",
            ),
        }
