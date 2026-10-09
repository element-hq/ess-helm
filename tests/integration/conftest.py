# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import os

import pytest

pytest_plugins = [
    "integration.fixtures",
]


# this overrides the pytest_kubernetes autouse teardown fixture
# to make it compatible with asyncio_cooperative by making it an async fixture
# In theory it would be used to teardown cached clusters, but we do not use this feature
# in our pytest test suite. Our `cluster` fixture takes care of the teardown itself.
@pytest.fixture(scope="session", autouse=True)
def remaining_clusters_teardown():
    return


# pytest-asyncio-cooperative fills the fixtures of the marked tests itself. It then clears
# item.fixturenames, so the regular fixture setup does not run them again. But it clears
# them only after the fill: when the fill fails, the regular setup runs the fixtures
# synchronously. Async fixtures return raw coroutines then, and the resulting error masks
# the real one (e.g. a skip becomes a TypeError deep inside another fixture). Clear the
# names here instead: the regular setup does nothing, and the real error raises.
# It's a hook implementation of https://github.com/element-hq/pytest-asyncio-cooperative/pull/2/changes
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if "asyncio_cooperative" in item.keywords:
        item.fixturenames = []


def pytest_addoption(parser):
    parser.addoption("--env-setup", action="store_true", default=False, help="run test env setup")


def pytest_configure(config):
    config.addinivalue_line("markers", "env_setup: mark test as run only when doing env setup")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--env-setup"):
        skip_tests = pytest.mark.skip(reason="running with --env-setup, skipping test")

        for item in items:
            if "env_setup" not in item.keywords:
                item.add_marker(skip_tests)

    else:
        skip_env_setup = pytest.mark.skip(reason="need --env-setup option to run")

        if not os.environ.get("TEST_VALUES_FILE"):
            pytest.exit("TEST_VALUES_FILE is not set")

        for item in items:
            if "env_setup" in item.keywords:
                item.add_marker(skip_env_setup)
