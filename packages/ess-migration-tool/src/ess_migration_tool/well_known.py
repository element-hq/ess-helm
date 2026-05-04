# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Well Known delegation migration strategy."""

import json
import logging
from typing import Any

from .migration import ConfigValueTransformer, MigrationStrategy, TransformationSpec
from .models import GlobalOptions
from .utils import extract_hostname_from_url

logger = logging.getLogger("migration")

WELL_KNOWN_COMPONENT_ROOT_KEY = "wellKnownDelegation"

# File name patterns for each well-known type
WELL_KNOWN_FILE_PATTERNS: dict[str, list[str]] = {
    "client": ["client", "client.json"],
    "server": ["server", "server.json"],
    "support": ["support", "support.json"],
}

# Strategy names for each well-known type
WELL_KNOWN_STRATEGY_NAMES: dict[str, str] = {
    "client": "Well Known Client",
    "server": "Well Known Server",
    "support": "Well Known Support",
}


def to_json_string(_: ConfigValueTransformer, value: Any, **__: Any) -> str:
    """Transform a value to a JSON string."""
    if value is None:
        return "{}"
    return json.dumps(value)


class WellKnownMigration(MigrationStrategy):
    """Well Known delegation migration implementation.

    Parameterized by well_known_type which can be "client", "server", or "support".
    """

    def __init__(self, global_options: GlobalOptions, well_known_type: str) -> None:
        self.global_options = global_options
        self.well_known_type = well_known_type

    @property
    def name(self) -> str:
        return WELL_KNOWN_STRATEGY_NAMES[self.well_known_type]

    @property
    def override_configs(self) -> set[str]:
        """Well-known configs are all user-provided, no ESS-managed overrides."""
        return set()

    @property
    def underride_configs(self) -> set[str]:
        """Well-known configs override ESS defaults (m.homeserver, m.server) - this is intentional."""
        return set()

    @property
    def transformations(self) -> list[TransformationSpec]:
        """Get transformations for this well-known type."""
        transformations: list[TransformationSpec] = [
            # Enable well-known delegation (harmless if set multiple times)
            TransformationSpec(
                src_key=None,
                target_key="wellKnownDelegation.enabled",
                transformer=lambda *_, **__: True,
            ),
        ]

        # For client well-known type, extract server_name and base_url
        if self.well_known_type == "client":
            transformations.extend(
                [
                    # Extract server_name from m.homeserver.server_name
                    TransformationSpec(
                        src_key="'m.homeserver'.server_name",
                        target_key="serverName",
                        required=False,
                    ),
                    # Extract base_url from m.homeserver.base_url and map to synapse.ingress.host
                    TransformationSpec(
                        src_key="'m.homeserver'.base_url",
                        target_key="synapse.ingress.host",
                        transformer=extract_hostname_from_url,
                        required=False,
                    ),
                ]
            )

        # Map the full config to additional.<type> as JSON string
        transformations.append(
            TransformationSpec(
                src_key=None,
                target_key=f"wellKnownDelegation.additional.{self.well_known_type}",
                transformer=to_json_string,
                required=False,
            )
        )

        return transformations
