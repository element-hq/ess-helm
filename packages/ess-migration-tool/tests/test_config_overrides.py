# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Tests to verify that override_configs and underride_configs don't conflict.
"""

import pytest
from ess_migration_tool.element_web import ElementWebMigration
from ess_migration_tool.hookshot import HookshotMigration
from ess_migration_tool.mas import MASMigration
from ess_migration_tool.models import GlobalOptions
from ess_migration_tool.synapse import SynapseMigration
from ess_migration_tool.well_known import WellKnownMigration

# List of all migration strategies to test with their required arguments
# Each entry is a tuple of (StrategyClass, kwargs_to_pass_to_init)
STRATEGIES = [
    (SynapseMigration, {}),
    (MASMigration, {}),
    (HookshotMigration, {}),
    (ElementWebMigration, {}),
    (WellKnownMigration, {"well_known_type": "client"}),
    (WellKnownMigration, {"well_known_type": "server"}),
    (WellKnownMigration, {"well_known_type": "support"}),
    (WellKnownMigration, {"well_known_type": "element.json"}),
]


@pytest.fixture(params=STRATEGIES)
def strategy(request):
    """Fixture that provides each strategy instance."""
    strategy_class, init_kwargs = request.param
    return strategy_class(GlobalOptions(), **init_kwargs)


def test_override_underride_no_conflict(strategy):
    """Test that override_configs and underride_configs are disjoint sets."""
    override_configs = strategy.override_configs
    underride_configs = strategy.underride_configs

    # Check that both sets are defined
    assert override_configs is not None, f"{strategy.name}: override_configs is None"
    assert underride_configs is not None, f"{strategy.name}: underride_configs is None"

    # Check for conflicts
    conflict = override_configs & underride_configs
    assert conflict == set(), (
        f"{strategy.name}: Config keys appear in both override_configs and underride_configs: {conflict}"
    )


def test_all_strategies_have_defined_configs():
    """Test that all strategies define both override_configs and underride_configs."""
    for strategy_class, init_kwargs in STRATEGIES:
        strategy = strategy_class(GlobalOptions(), **init_kwargs)
        assert hasattr(strategy, "override_configs"), f"{strategy.name} missing override_configs"
        assert hasattr(strategy, "underride_configs"), f"{strategy.name} missing underride_configs"

        override_configs = strategy.override_configs
        underride_configs = strategy.underride_configs

        assert isinstance(override_configs, set), f"{strategy.name}: override_configs is not a set"
        assert isinstance(underride_configs, set), f"{strategy.name}: underride_configs is not a set"
