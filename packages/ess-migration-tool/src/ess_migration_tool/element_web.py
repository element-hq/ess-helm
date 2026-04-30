# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Element Web-specific migration strategy.
"""

import logging
from typing import Any

from .interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec, additional_config_transformer
from .models import DiscoveredSecret, GlobalOptions, SecretConfig
from .utils import extract_hostname_from_url

logger = logging.getLogger("migration")

ELEMENT_WEB_STRATEGY_NAME = "Element Web"
ELEMENT_WEB_COMPONENT_ROOT_KEY = "elementWeb"


class ElementWebMigration(MigrationStrategy):
    """Element Web-specific migration implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def name(self) -> str:
        return ELEMENT_WEB_STRATEGY_NAME

    @property
    def override_configs(self) -> set[str]:
        """Config keys that are managed by ESS and should be filtered out."""
        return {
            "setting_defaults.urlPreviewsEnabled",
            "setting_defaults.UIFeature.registration",
            "setting_defaults.UIFeature.passwordReset",
            "setting_defaults.UIFeature.deactivate",
            "setting_defaults.feature_group_calls",
            "default_server_config",
            "features",
            "element_call",
            "embedded_pages",
            "sso_redirect_options",
            "bug_report_endpoint_url",
            "map_style_url",
            "mobile_guide_app_variant",
        }

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get transformations for Element Web configuration."""

        def element_web_additional_transformer(
            config_value_transformer: "ConfigValueTransformer",
            value: Any,
            **kw: Any,
        ) -> dict[str, Any]:
            """Transform Element Web config to additional config."""
            return additional_config_transformer(
                config_value_transformer,
                value,
                component_root_key=ELEMENT_WEB_COMPONENT_ROOT_KEY,
                override_configs=self.override_configs,
                component_name=ELEMENT_WEB_STRATEGY_NAME,
                **kw,
            )

        return [
            # Enable Element Web component
            TransformationSpec(
                src_key=None,
                target_key="elementWeb.enabled",
                transformer=lambda *_, **__: True,
            ),
            # Map default_server_config.'m.homeserver'.server_name to global serverName
            TransformationSpec(
                src_key="default_server_config.'m.homeserver'.server_name",
                target_key="serverName",
                required=False,
            ),
            # Map default_server_config.'m.homeserver'.base_url to synapse.ingress.host
            TransformationSpec(
                src_key="default_server_config.'m.homeserver'.base_url",
                target_key="synapse.ingress.host",
                transformer=extract_hostname_from_url,
                required=False,
            ),
            # Transform remaining Element Web config to elementWeb.additional
            TransformationSpec(
                src_key=None,
                target_key="elementWeb.additional",
                transformer=element_web_additional_transformer,
                required=False,
            ),
        ]

    @property
    def component_config_extras(self) -> dict[str, Any]:
        return {"enabled": True}


class ElementWebSecretDiscovery(SecretDiscoveryStrategy):
    """Element Web-specific secret discovery implementation."""

    def __init__(self, global_options: GlobalOptions):
        self.global_options = global_options

    @property
    def ess_secret_schema(self) -> dict[str, SecretConfig]:
        """
        Get the ESS secret schema for Element Web.

        Element Web configuration (config.json) typically doesn't contain secrets.
        Secrets for Element Web are usually provided separately or through other means.
        """
        return {}

    @property
    def secret_name(self) -> str:
        return "element-web"

    def discover_component_specific_secrets(
        self, source_file: str, config_data: dict
    ) -> tuple[dict[str, DiscoveredSecret], list[tuple[DiscoveredSecret, str]]]:
        """
        Discover component-specific secrets from Element Web configuration.

        Element Web doesn't have specialized secret discovery, so this returns empty.

        Args:
            source_file: Source configuration file name
            config_data: Element Web configuration data

        Returns:
            Tuple of (empty dict, empty list) - no specialized secret discovery for Element Web
        """
        return ({}, [])


class ElementWebExtraFileDiscovery(ExtraFilesDiscoveryStrategy):
    """Element Web-specific extra file discovery implementation."""

    @property
    def component_name(self) -> str:
        return ELEMENT_WEB_STRATEGY_NAME

    @property
    def component_root_key(self) -> str:
        return ELEMENT_WEB_COMPONENT_ROOT_KEY

    @property
    def ignored_config_keys(self) -> list[str]:
        """Config keys to ignore when discovering extra files."""
        # Element Web doesn't have file path configurations in its config.json
        # that need special handling
        return []

    @property
    def ignored_file_paths(self) -> list[str]:
        """Files paths to ignore when discovering extra files."""
        return []
