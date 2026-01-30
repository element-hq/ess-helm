# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

pytest_plugins = [
    "integration.fixtures",
]


# this overrides the pytest_kubernetes autouse teardown fixture
# to make it compatible with asyncio_cooperative by making it an async fixture
# In theory it would be used to teardown cached clusters, but we do not use this feature
# in our pytest test suite. Our `cluster` fixture takes care of the teardown itself.
@pytest.fixture(scope="session", autouse=True)
async def remaining_clusters_teardown():
    return
