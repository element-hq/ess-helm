# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Element Web migration."""

import logging

from ess_migration_tool.element_web import ElementWebMigration
from ess_migration_tool.migration import ConfigValueTransformer
from ess_migration_tool.models import GlobalOptions


def test_element_web_additional_config_excludes_default_server_config():
    """Test that default_server_config values are extracted and m.homeserver is empty in additional config."""
    transformer = ConfigValueTransformer(logging.getLogger(), ess_config={})
    migration = ElementWebMigration(GlobalOptions())

    config = {
        "default_server_config": {"m.homeserver": {"base_url": "https://matrix.example.com"}},
        "setting_defaults": {"customTheme": True},
    }

    transformer.transform_from_config(config, migration.transformations)

    import yaml

    additional_config = yaml.safe_load(transformer.ess_config["elementWeb"]["additional"]["00-imported.yaml"]["config"])
    # Verify that m.homeserver is empty (values extracted)
    assert additional_config["default_server_config"]["m.homeserver"] == {}
    assert "customTheme" in additional_config["setting_defaults"]
    # Verify that synapse.ingress.host was set from the base_url
    assert transformer.ess_config["synapse"]["ingress"]["host"] == "matrix.example.com"
