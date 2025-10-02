# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from .fixtures import ESSData
from .lib.utils import aiohttp_client, value_file_has


@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_admin_can_access_root(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("element-admin")

    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            "https://127.0.0.1/",
            headers={"Host": f"admin.{generated_data.server_name}"},
            server_hostname=f"admin.{generated_data.server_name}",
        ) as response,
    ):
        assert response.status == 200
