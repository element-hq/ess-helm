# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Hookshot-specific migration strategy.
"""

import logging
from typing import TYPE_CHECKING, Any

from .interfaces import ExtraFilesDiscoveryStrategy, MigrationStrategy, SecretDiscoveryStrategy
from .migration import TransformationSpec, additional_config_transformer
from .models import DiscoverableSecret, GlobalOptions, SecretConfig

if TYPE_CHECKING:
    from .migration import ConfigValueTransformer

logger = logging.getLogger("migration")

HOOKSHOT_STRATEGY_NAME = "Hookshot"
HOOKSHOT_COMPONENT_ROOT_KEY = "hookshot"


class HookshotMigration(MigrationStrategy):
    """Hookshot-specific migration implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def name(self) -> str:
        return HOOKSHOT_STRATEGY_NAME

    @property
    def override_configs(self) -> set[str]:
        """Config keys that are managed by ESS (users should not override these)."""
        return {
            "bridge.domain",
            "bridge.url",
            "bridge.port",
            "bridge.bindAddress",
            "listeners",
            "passFile",
            "cache.redisUri",
            "encryption.storagePath",
            "matrix",
            "telemery",
            "database",
            "http",
        }

    @property
    def underride_configs(self) -> set[str]:
        """Config keys that are ESS defaults (users can override these via additional config)."""
        return {"widgets.roomSetupWidget.addOnInvite", "permissions"}

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get transformations for Hookshot configuration."""

        def hookshot_additional_transformer(
            config_value_transformer: "ConfigValueTransformer",
            value: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Transform Hookshot config to additional config."""
            return additional_config_transformer(
                config_value_transformer,
                value,
                component_root_key=HOOKSHOT_COMPONENT_ROOT_KEY,
                override_configs=self.override_configs,
                underride_configs=self.underride_configs,
                component_name=HOOKSHOT_STRATEGY_NAME,
                serialization_format="yaml",
                use_file_object_format=True,
                **kwargs,
            )

        return [
            # Enable Hookshot component
            TransformationSpec(
                src_key=None,
                target_key="hookshot.enabled",
                transformer=lambda *_, **__: True,
            ),
            # Map bridge.domain to global serverName
            TransformationSpec(
                src_key="bridge.domain",
                target_key="serverName",
                required=True,
            ),
            # Map logging.level to hookshot.logging.level
            TransformationSpec(
                src_key="logging.level",
                target_key="hookshot.logging.level",
                required=False,
            ),
            # Map user.localpart to hookshot.user.localpart
            TransformationSpec(
                src_key="user.localpart",
                target_key="hookshot.user.localpart",
                required=False,
            ),
            # Map enableEncryption to hookshot.enableEncryption
            TransformationSpec(
                src_key="enableEncryption",
                target_key="hookshot.enableEncryption",
                required=False,
            ),
            # Transform remaining Hookshot config to hookshot.additional
            TransformationSpec(
                src_key=None,
                target_key="hookshot.additional",
                transformer=hookshot_additional_transformer,
                required=False,
            ),
        ]


class HookshotSecretDiscovery(SecretDiscoveryStrategy):
    """Hookshot-specific secret discovery implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def ess_secret_schema(self) -> dict[str, DiscoverableSecret]:
        """Get the ESS secret schema for Hookshot."""
        return {
            "hookshot.appserviceRegistration": DiscoverableSecret(
                description="Hookshot appservice registration file",
                optional=True,
                init_if_missing_from_source_cfg=True,
                discovery=None,
            ),
            "hookshot.passkey": DiscoverableSecret(
                description="Hookshot passkey for token encryption",
                optional=True,
                init_if_missing_from_source_cfg=True,
                discovery=SecretConfig(
                    config_inline=None,
                    config_path="passFile",
                ),
            ),
        }

    @property
    def name(self) -> str:
        return HOOKSHOT_STRATEGY_NAME

    @property
    def secret_name(self) -> str:
        return "hookshot"

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict
    ) -> tuple[dict[str, Any], list[tuple[Any, str]]]:
        """
        Discover Hookshot-specific secrets from configuration.

        Args:
            source_file: Source configuration file name
            config_data: Hookshot configuration data

        Returns:
            Tuple of (empty dict, empty list) - Hookshot uses standard secret discovery
        """
        # Hookshot uses the standard generic secret discovery mechanism
        # via the ess_secret_schema (config_path for passFile, etc.)
        return ({}, [])


class HookshotExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    """Hookshot-specific extra file discovery implementation."""

    @property
    def component_name(self) -> str:
        return HOOKSHOT_STRATEGY_NAME

    @property
    def component_root_key(self) -> str:
        return HOOKSHOT_COMPONENT_ROOT_KEY

    @property
    def ignored_config_keys(self) -> list[str]:
        """Config keys to ignore when discovering extra files."""
        return [
            "passFile",  # Handled by secret discovery
            "encryption.storagePath",  # Managed by ESS storage, not extra files
        ]

    @property
    def ignored_file_paths(self) -> list[str]:
        """File paths to ignore when discovering extra files."""
        return []
