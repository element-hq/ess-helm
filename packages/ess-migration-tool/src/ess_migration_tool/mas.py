# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
MAS-specific migration strategy.
"""

import logging
import os
from typing import Any

from .interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec, additional_config_transformer
from .models import DiscoverableSecret, DiscoveredSecret, GlobalOptions, SecretConfig
from .utils import (
    detect_key_type,
    extract_hostname_from_url,
    extract_port_from_uri,
    parse_postgres_uri,
    yaml_dump_with_pipe_for_multiline,
)

logger = logging.getLogger("migration")

MAS_STRATEGY_NAME = "Matrix Authentication Service"
MAS_COMPONENT_ROOT_KEY = "matrixAuthenticationService"


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
            "telemetry",  # Telemetry configuration is managed by ESS
            "matrix",  # Matrix configuration is managed by ESS
        }

    @property
    def underride_configs(self) -> set[str]:
        """Config keys that are ESS defaults (users can override these via additional config)."""
        return {
            "policy.data.admin_clients",
            "policy.data.admin_users",
            "policy.data.client_registration.allow_host_mismatch",
            "policy.data.client_registration.allow_insecure_uris",
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
                underride_configs=self.underride_configs,
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
            # matrix.homeserver -> serverName (maps to same ESS path as Synapse's server_name)
            TransformationSpec(
                src_key="matrix.homeserver",
                target_key="serverName",
                required=True,
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
            # ... other non-database transformations ...
        ]

        if self.global_options.use_existing_database:
            # External database: import database configuration
            transformations = base_transformations + [
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
            transformations = base_transformations + [
                TransformationSpec(
                    src_key="database",  # Trigger on database section
                    target_key="postgres.enabled",
                    transformer=lambda _, __, **kw: True,  # Set to True for ESS-managed PostgreSQL
                )
            ]
        return transformations + [
            TransformationSpec(
                src_key=None,
                target_key="matrixAuthenticationService.additional",
                transformer=mas_additional_transformer,
                required=False,
            ),  # Generic additional config generation (src_key=None passes full config)
        ]


class MASSecretDiscovery(SecretDiscoveryStrategy):
    """MAS-specific secret discovery implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def secret_name(self) -> str:
        return "matrix-authentication-service"

    @property
    def name(self) -> str:
        return MAS_STRATEGY_NAME

    @property
    def ess_secret_schema(self) -> dict[str, DiscoverableSecret]:
        """Get the ESS secret schema for MAS."""
        schema: dict[str, DiscoverableSecret] = {
            # MAS secrets
        }

        # Only include PostgreSQL password when using existing database
        if self.global_options.use_existing_database:
            schema["matrixAuthenticationService.postgres.password"] = DiscoverableSecret(
                description="MAS database password",
                init_if_missing_from_source_cfg=False,  # Must be provided if using existing db
                discovery=SecretConfig(
                    config_inline="database.uri",
                    config_path=None,
                    transformer=lambda uri, **kw: parse_postgres_uri(uri).get("password"),
                ),
            )

        # Other MAS secrets (always included)
        schema.update(
            {
                "matrixAuthenticationService.synapseSharedSecret": DiscoverableSecret(
                    description="MAS Synapse shared secret",
                    init_if_missing_from_source_cfg=True,  # Can be auto-generated
                    takes_precedence_if_duplicates=True,  # MAS owns this secret when discovered by multiple strategies
                    discovery=SecretConfig(
                        config_inline="matrix.secret",
                        config_path="matrix.secret_file",
                    ),
                ),
                "matrixAuthenticationService.encryptionSecret": DiscoverableSecret(
                    description="MAS encryption secret",
                    init_if_missing_from_source_cfg=True,  # Must be provided
                    discovery=SecretConfig(
                        config_inline="secrets.encryption",
                        config_path="secrets.encryption_file",
                    ),
                ),
                # Key secrets - these will be discovered through special key processing
                "matrixAuthenticationService.privateKeys.rsa": DiscoverableSecret(
                    description="MAS RSA private key for signing operations",
                    init_if_missing_from_source_cfg=True,
                    discovery=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaPrime256v1": DiscoverableSecret(
                    description="MAS ECDSA Prime256v1 private key for signing operations",
                    init_if_missing_from_source_cfg=True,
                    discovery=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaSecp256k1": DiscoverableSecret(
                    description="MAS ECDSA Secp256k1 private key for signing operations",
                    optional=True,  # This key type is optional
                    init_if_missing_from_source_cfg=False,
                    discovery=None,
                ),
                "matrixAuthenticationService.privateKeys.ecdsaSecp384r1": DiscoverableSecret(
                    description="MAS ECDSA Secp384r1 private key for signing operations",
                    optional=True,  # This key type is optional
                    init_if_missing_from_source_cfg=False,
                    discovery=None,
                ),
            }
        )

        return schema

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Discover component-specific secrets from MAS configuration.

        Args:
            source_file: Source configuration file name
            config_data: MAS configuration data

        Returns:
            Tuple of (discovered_secrets, failed_secrets) where:
            - discovered_secrets: Dictionary mapping ESS secret keys to DiscoveredSecret objects
            - failed_secrets: List of (DiscoveredSecret, error_message) tuples for secrets
              that failed to be read. DiscoveredSecret includes config_key from the source config.
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}
        failed_secrets: list[tuple[DiscoveredSecret, str]] = []

        # Handle keys_dir (directory scanning)
        keys_dir = config_data.get("secrets", {}).get("keys_dir")
        if keys_dir:
            dir_secrets, dir_failures = self._process_keys_directory(source_file, keys_dir)
            discovered_secrets.update(dir_secrets)
            # Directory failures are logged but not returned for prompting

        # Handle individual keys
        keys_config = config_data.get("secrets", {}).get("keys", [])
        if keys_config:
            individual_secrets, individual_failures = self._process_individual_keys(source_file, keys_config)
            # Individual keys take precedence over directory keys
            discovered_secrets.update(individual_secrets)
            failed_secrets.extend(individual_failures)

        return (discovered_secrets, failed_secrets)

    def _process_keys_directory(
        self, source_file: str, keys_dir: str
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Process all key files in a directory.

        Args:
            source_file: Source configuration file name
            keys_dir: Path to directory containing key files

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
            Note: failed_secrets is always empty list as directory scan failures are only logged
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}
        try:
            if not os.path.isdir(keys_dir):
                logger.warning(f"Keys directory does not exist: {keys_dir}")
                return (discovered_secrets, [])

            for filename in os.listdir(keys_dir):
                filepath = os.path.join(keys_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        with open(filepath, "rb") as f:
                            content = f.read()
                        key_type = detect_key_type(content)
                        if key_type in ["rsa", "ecdsaPrime256v1", "ecdsaSecp256k1", "ecdsaSecp384r1"]:
                            ess_secret_key = f"matrixAuthenticationService.privateKeys.{key_type}"
                            source_config_key = "secrets.keys_dir"
                            # Only set if not already discovered (prefer individual keys over directory)
                            if ess_secret_key not in discovered_secrets:
                                discovered_secret = DiscoveredSecret(
                                    source_file=source_file,
                                    secret_key=ess_secret_key,
                                    config_key=source_config_key,
                                    value=content.decode("utf-8"),
                                )
                                discovered_secrets[ess_secret_key] = discovered_secret
                                logger.info(f"Discovered {key_type} key from file: {filepath}")
                    except Exception as e:
                        # Only log failures for directory scanning; directory scan failures cannot be prompted
                        logger.warning(f"Failed to process key file {filepath}: {e}")
        except Exception as e:
            logger.warning(f"Failed to process keys directory {keys_dir}: {e}")

        return (discovered_secrets, [])

    def _process_individual_keys(
        self, source_file: str, keys_config: list
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Process individual key configurations.

        Args:
            source_file: Source configuration file name
            keys_config: List of key configuration dictionaries

        Returns:
            Tuple of (discovered_secrets, failed_secrets)
        """
        discovered_secrets: dict[str, DiscoveredSecret] = {}
        failed_secrets: list[tuple[DiscoveredSecret, str]] = []

        for index, key_config in enumerate(keys_config):
            content = None
            source_config_key = None

            # Try key_file first
            if "key_file" in key_config:
                source_config_key = f"secrets.keys.{index}"
                try:
                    with open(key_config["key_file"], "rb") as f:
                        content = f.read()
                    logger.info(f"Read key from file: {key_config['key_file']}")
                except Exception as e:
                    # Track failure for prompting
                    ess_secret_key = f"matrixAuthenticationService.privateKeys.{index}"
                    error_msg = f"Failed to read key file {key_config['key_file']}: {e}"
                    failed_secret = DiscoveredSecret(
                        source_file=source_file,
                        secret_key=ess_secret_key,
                        config_key=source_config_key,
                        value="",
                    )
                    failed_secrets.append((failed_secret, error_msg))
                    logger.warning(error_msg)
                    continue

            # Try inline key content
            elif "key" in key_config:
                content = key_config["key"].encode("utf-8")
                source_config_key = f"secrets.keys.{index}"
                logger.info("Read key from inline content")

            if content and source_config_key:
                key_type = detect_key_type(content)
                if key_type in ["rsa", "ecdsaPrime256v1", "ecdsaSecp256k1", "ecdsaSecp384r1"]:
                    ess_secret_key = f"matrixAuthenticationService.privateKeys.{key_type}"
                    # Only set if not already discovered (prefer individual keys over directory)
                    if ess_secret_key not in discovered_secrets:
                        discovered_secret = DiscoveredSecret(
                            source_file=source_file,
                            secret_key=ess_secret_key,
                            config_key=source_config_key,
                            value=content.decode("utf-8"),
                        )
                        discovered_secrets[ess_secret_key] = discovered_secret
                        logger.info(f"Discovered {key_type} key from individual configuration")

        return (discovered_secrets, failed_secrets)


class MASExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    @property
    def component_name(self) -> str:
        return MAS_STRATEGY_NAME

    @property
    def component_root_key(self) -> str:
        return MAS_COMPONENT_ROOT_KEY

    @property
    def ignored_config_keys(self) -> list[str]:
        # Keep secrets.keys_dir and secrets.keys in ignored keys for extra files discovery
        # as they are processed by specialized key discovery logic
        return ["secrets.keys_dir", "secrets.keys"]

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        ...
        return []
