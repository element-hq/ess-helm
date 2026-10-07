# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import os

import pytest

from .lib import docker_playwright

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


def pytest_addoption(parser):
    parser.addoption("--env-setup", action="store_true", default=False, help="run test env setup")


def pytest_configure(config):
    config.addinivalue_line("markers", "env_setup: mark test as run only when doing env setup")
    config.addinivalue_line(
        "markers",
        "docker_playwright: run the body of the test in the playwright container (requires asyncio_cooperative)",
    )
    docker_playwright.install()


def pytest_sessionfinish(session, exitstatus):
    docker_playwright.stop_container()


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "docker_playwright" in item.keywords and "asyncio_cooperative" not in item.keywords:
            pytest.exit(f"{item.nodeid} is marked docker_playwright but not asyncio_cooperative")

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
