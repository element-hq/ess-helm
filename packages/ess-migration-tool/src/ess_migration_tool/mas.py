# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
MAS-specific migration strategy.
"""

import logging
import os
import urllib
from typing import Any

from .interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec, additional_config_transformer
from .models import DiscoveredSecret, GlobalOptions, SecretConfig
from .utils import detect_key_type, extract_hostname_from_url, yaml_dump_with_pipe_for_multiline

logger = logging.getLogger("migration")

MAS_STRATEGY_NAME = "Matrix Authentication Service"
MAS_COMPONENT_ROOT_KEY = "matrixAuthenticationService"


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


def extract_port_from_uri(_, uri: str, **kwargs: Any) -> int | None:
    """
    Extract port from PostgreSQL URI, returning None if not present.

    Args:
        uri: PostgreSQL connection URI
        **kwargs: Optional context parameters (unused)

    Returns:
        Port as integer if present, None otherwise
    """
    parsed = parse_postgres_uri(uri)
    port = parsed.get("port")
    return int(port) if port is not None else None


def filter_mas_listeners(_, listeners: list[dict] | None, **kwargs: Any) -> dict[str, Any] | None:
    """
    Filter out listeners that are managed by the ESS chart for MAS.

    The chart manages listeners that serve specific resources on specific ports.
    This function removes listeners that serve only ESS-managed resources and keeps custom listeners,
    returning them as a dictionary structure for additional config.

    Args:
        listeners: List of listener configurations from source MAS config
        **kwargs: Optional context parameters (unused)

    Returns:
        Dictionary with listeners.yml config structure, or None if no custom listeners remain
    """
    if not listeners:
        return None

    # Resources managed by the ESS chart that should be filtered out
    chart_managed_resources = {
        "human",
        "discovery",
        "oauth",
        "compat",
        "assets",
        "graphql",
        "adminapi",
        "health",
        "prometheus",
        "connection-info",
    }

    # Ports managed by the ESS chart that should be filtered out
    chart_managed_ports = {8080, 8081}

    filtered_listeners = []
    for listener in listeners:
        # Get the listener binds
        binds = listener.get("binds", [])

        # Check if any of the binds use chart-managed ports
        any_managed_port = False
        has_incompatible_binds = False
        listener_port = None

        for bind in binds:
            # Format 1: address with port (e.g., "[::]:8080")
            if "address" in bind:
                address = bind["address"]
                try:
                    last_colon_pos = address.rfind(":")
                    if last_colon_pos != -1:
                        port_str = address[last_colon_pos + 1 :]
                        if port_str:
                            listener_port = int(port_str)
                except ValueError:
                    # Log invalid port format and skip this bind
                    logger.debug("Invalid port format in address: %s", address)
                    continue

            # Format 2: host and port combination
            elif "port" in bind:
                listener_port = bind["port"]

            # Format 3: UNIX socket - incompatible with ESS
            elif "socket" in bind:
                has_incompatible_binds = True
                logger.debug("Filtered out listener using UNIX socket: %s", bind["socket"])
                break

            # Format 4: file descriptor - incompatible with ESS
            elif "fd" in bind:
                has_incompatible_binds = True
                logger.debug("Filtered out listener using file descriptor: %s", bind["fd"])
                break

            # Check if this port is managed
            if listener_port is not None and listener_port in chart_managed_ports:
                any_managed_port = True
                logger.debug("Filtered out listener using managed port: %s", listener_port)
                break

        # Filter out listeners that use chart-managed ports or incompatible binds
        if any_managed_port or has_incompatible_binds:
            continue

        # Skip listeners that have no valid binds (all binds had invalid ports)
        if listener_port is None:
            logger.debug("Filtered out listener with no valid binds")
            continue

        # Filter resources: keep only non-chart-managed resources
        filtered_resources = []
        original_resources = listener.get("resources", [])

        for resource in original_resources:
            resource_name = resource.get("name")
            if resource_name and resource_name not in chart_managed_resources:
                filtered_resources.append(resource)

        # Keep listener only if it has any custom resources left
        if filtered_resources:
            new_listener = listener.copy()
            new_listener["resources"] = filtered_resources
            filtered_listeners.append(new_listener)
            logger.debug(
                f"Importing listener {listener_port} with filtered resources:"
                f"{','.join([r['name'] for r in filtered_resources])}"
            )
        else:
            logger.debug(f"Filtered out listener port {listener_port} with only chart-managed resources")

    if not filtered_listeners:
        return None

    # Return the structure for additional config
    return {"listeners.yml": {"config": yaml_dump_with_pipe_for_multiline({"http": {"listeners": filtered_listeners}})}}


class MASMigration(MigrationStrategy):
    """MAS-specific migration implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def name(self) -> str:
        return MAS_STRATEGY_NAME

    @property
    def override_configs(self) -> set[str]:
        return {
            "http",  # The entire HTTP configuration is managed by ESS
            "database.uri",  # Database URI configuration is managed by ESS"
        }

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get transformations based on database choice."""

        # Lambda to wrap additional_config_transformer with MAS-specific context
        def mas_additional_transformer(
            config_value_transformer: "ConfigValueTransformer",
            value: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return additional_config_transformer(
                config_value_transformer,
                value,
                component_root_key=MAS_COMPONENT_ROOT_KEY,
                override_configs=self.override_configs,
                component_name=MAS_STRATEGY_NAME,
                **kwargs,
            )

        base_transformations = [
            # Enable MAS component
            TransformationSpec(
                src_key=None,
                target_key="matrixAuthenticationService.enabled",
                transformer=lambda *_, **__: True,
            ),
            TransformationSpec(
                src_key="http.public_base",
                target_key="matrixAuthenticationService.ingress.host",
                transformer=extract_hostname_from_url,
            ),  # Extract hostname from http.public_base for ingress host
            TransformationSpec(
                src_key="http.listeners",
                target_key="matrixAuthenticationService.additional",
                transformer=filter_mas_listeners,
                required=False,
            ),  # Filter out chart-managed listeners and output to additional config
            TransformationSpec(
                src_key=None,
                target_key="matrixAuthenticationService.additional",
                transformer=mas_additional_transformer,
                required=False,
            ),  # Generic additional config generation (src_key=None passes full config)
            # ... other non-database transformations ...
        ]

        if self.global_options.use_existing_database:
            # External database: import database configuration
            return base_transformations + [
                TransformationSpec(
                    src_key="database.uri",
                    target_key="matrixAuthenticationService.postgres.host",
                    transformer=lambda _, uri, **kw: parse_postgres_uri(uri).get("host"),
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
                    transformer=lambda _, uri, **kw: parse_postgres_uri(uri).get("user"),
                    required=True,
                ),
                TransformationSpec(
                    src_key="database.uri",
                    target_key="matrixAuthenticationService.postgres.database",
                    transformer=lambda _, uri, **kw: parse_postgres_uri(uri).get("name"),
                    required=True,
                ),
                TransformationSpec(
                    src_key="database.uri",
                    target_key="matrixAuthenticationService.postgres.sslMode",
                    transformer=lambda _, uri, **kw: parse_postgres_uri(uri).get("ssl"),
                    required=False,
                ),
                # ... other database property transformations ...
            ]
        else:
            # ESS-managed: set postgres.enabled flag
            return base_transformations + [
                TransformationSpec(
                    src_key="database",  # Trigger on database section
                    target_key="postgres.enabled",
                    transformer=lambda _, __, **kw: True,  # Set to True for ESS-managed Postgres
                )
            ]


class MASSecretDiscovery(SecretDiscoveryStrategy):
    """MAS-specific secret discovery implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def component_name(self) -> str:
        return "Matrix Authentication Service"

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """Get the ESS secret schema for MAS."""
        schema = {
            # MAS secrets
        }

        # Only include PostgreSQL password when using existing database
        if self.global_options.use_existing_database:
            schema["matrixAuthenticationService.postgres.password"] = SecretConfig(
                init_if_missing_from_source_cfg=True,  # Must be provided
                description="MAS database password",
                config_inline="database.uri",
                config_path=None,
                transformer=lambda uri, **kw: parse_postgres_uri(uri).get("password"),
            )

        # Other MAS secrets (always included)
        schema.update(
            {
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
                # Key secrets - these will be discovered through special key processing
                "matrixAuthenticationService.privateKeys.rsa": SecretConfig(
                    init_if_missing_from_source_cfg=True,
                    description="MAS RSA private key for signing operations",
                    config_inline=None,
                    config_path=None,
                    transformer=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaPrime256v1": SecretConfig(
                    init_if_missing_from_source_cfg=True,
                    description="MAS ECDSA Prime256v1 private key for signing operations",
                    config_inline=None,
                    config_path=None,
                    transformer=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaSecp256k1": SecretConfig(
                    init_if_missing_from_source_cfg=False,
                    description="MAS ECDSA Secp256k1 private key for signing operations",
                    config_inline=None,
                    config_path=None,
                    optional=True,  # This key type is optional
                    transformer=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaSecp384r1": SecretConfig(
                    init_if_missing_from_source_cfg=False,
                    description="MAS ECDSA Secp384r1 private key for signing operations",
                    config_inline=None,
                    config_path=None,
                    optional=True,  # This key type is optional
                    transformer=None,
                ),
            }
        )

        return schema

    def discover_component_specific_secrets(self, config_data: dict) -> dict[str, DiscoveredSecret]:
        """
        Discover component-specific secrets from MAS configuration.

        Args:
            config_data: MAS configuration data

        Returns:
            Dictionary mapping ESS secret keys to DiscoveredSecret objects
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}

        # Handle keys_dir (directory scanning)
        keys_dir = config_data.get("secrets", {}).get("keys_dir")
        if keys_dir:
            dir_secrets = self._process_keys_directory(keys_dir)
            discovered_secrets.update(dir_secrets)

        # Handle individual keys
        keys_config = config_data.get("secrets", {}).get("keys", [])
        if keys_config:
            individual_secrets = self._process_individual_keys(keys_config)
            # Individual keys take precedence over directory keys
            discovered_secrets.update(individual_secrets)

        return discovered_secrets

    def _process_keys_directory(self, keys_dir: str) -> dict[str, DiscoveredSecret]:
        """
        Process all key files in a directory.

        Args:
            keys_dir: Path to directory containing key files

        Returns:
            Dictionary mapping ESS secret keys to DiscoveredSecret objects
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}
        try:
            if not os.path.isdir(keys_dir):
                logger.warning(f"Keys directory does not exist: {keys_dir}")
                return discovered_secrets

            for filename in os.listdir(keys_dir):
                filepath = os.path.join(keys_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        with open(filepath, "rb") as f:
                            content = f.read()
                        key_type = detect_key_type(content)
                        if key_type in ["rsa", "ecdsaPrime256v1", "ecdsaSecp256k1", "ecdsaSecp384r1"]:
                            secret_key = f"matrixAuthenticationService.privateKeys.{key_type}"
                            # Only set if not already discovered (prefer individual keys over directory)
                            if secret_key not in discovered_secrets:
                                discovered_secret = DiscoveredSecret(
                                    source_file="mas.yaml",
                                    secret_key=secret_key,
                                    config_key="secrets.keys_dir",
                                    value=content.decode("utf-8"),
                                )
                                discovered_secrets[secret_key] = discovered_secret
                                logger.info(f"Discovered {key_type} key from file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to process key file {filepath}: {e}")
        except Exception as e:
            logger.warning(f"Failed to process keys directory {keys_dir}: {e}")

        return discovered_secrets

    def _process_individual_keys(self, keys_config: list) -> dict[str, DiscoveredSecret]:
        """
        Process individual key configurations.

        Args:
            keys_config: List of key configuration dictionaries

        Returns:
            Dictionary mapping ESS secret keys to DiscoveredSecret objects
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}

        for index, key_config in enumerate(keys_config):
            content = None
            config_key = None

            # Try key_file first
            if "key_file" in key_config:
                try:
                    with open(key_config["key_file"], "rb") as f:
                        content = f.read()
                    config_key = f"secrets.privateKeys.{index}"
                    logger.info(f"Read key from file: {key_config['key_file']}")
                except Exception as e:
                    logger.warning(f"Failed to read key file {key_config['key_file']}: {e}")
                    continue

            # Try inline key content
            elif "key" in key_config:
                content = key_config["key"].encode("utf-8")
                config_key = f"secrets.privateKeys.{index}"
                logger.info("Read key from inline content")

            if content and config_key:
                key_type = detect_key_type(content)
                if key_type in ["rsa", "ecdsaPrime256v1", "ecdsaSecp256k1", "ecdsaSecp384r1"]:
                    secret_key = f"matrixAuthenticationService.privateKeys.{key_type}"
                    # Only set if not already discovered (prefer individual keys over directory)
                    if secret_key not in discovered_secrets:
                        discovered_secret = DiscoveredSecret(
                            source_file="mas.yaml",
                            secret_key=secret_key,
                            config_key=config_key,
                            value=content.decode("utf-8"),
                        )
                        discovered_secrets[secret_key] = discovered_secret
                        logger.info(f"Discovered {key_type} key from individual configuration")

        return discovered_secrets


class MASExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    @property
    def component_name(self) -> str:
        return MAS_STRATEGY_NAME

    @property
    def component_root_key(self) -> str:
        return MAS_COMPONENT_ROOT_KEY

    @property
    def ignored_config_keys(self) -> list[str]:
        # Keep secrets.keys_dir in ignored keys for extra files discovery
        # as it's processed by specialized key discovery logic
        return ["secrets.keys_dir"]

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        ...
        return []
