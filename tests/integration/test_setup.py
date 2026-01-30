# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest


# this test is only here to setup the environment using `--env-setup` arg
@pytest.mark.env_setup
@pytest.mark.asyncio_cooperative
async def test_setup():
    pytest.exit("k3d environment and dependent helm charts successfully setup", 0)
