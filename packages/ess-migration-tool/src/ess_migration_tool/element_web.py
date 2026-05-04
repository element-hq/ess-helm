# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Element Web-specific migration strategy.
"""

import logging
from typing import Any

from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec, additional_config_transformer
from .models import GlobalOptions
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
            """Transform Element Web config to additional config.

            Element Web expects additional[$key] to be a JSON string directly,
            not wrapped in a {"config": ...} object like Synapse and MAS.
            We use the shared additional_config_transformer with:
            - serialization_format="json" to output JSON
            - use_file_object_format=False to return {"filename": string} instead of {"filename": {"config": string}}
            """
            return additional_config_transformer(
                config_value_transformer,
                value,
                component_root_key=ELEMENT_WEB_COMPONENT_ROOT_KEY,
                override_configs=self.override_configs,
                component_name=ELEMENT_WEB_STRATEGY_NAME,
                serialization_format="json",
                use_file_object_format=False,
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
