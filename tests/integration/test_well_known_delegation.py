# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from .fixtures import ESSData
from .lib.utils import aiohttp_client, aiottp_get_json, value_file_has


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.asyncio_cooperative
async def test_well_known_files_can_be_accessed(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("well-known")

    json_content = await aiottp_get_json(f"https://{generated_data.server_name}/.well-known/matrix/client", ssl_context)
    if value_file_has("synapse.enabled", True):
        assert "m.homeserver" in json_content
    if value_file_has("matrixRTC.enabled", True):
        assert json_content["org.matrix.msc4143.rtc_foci"] == [
            {"type": "livekit", "livekit_service_url": f"https://mrtc.{generated_data.server_name}"}
        ]
    else:
        assert "org.matrix.msc4143.rtc_foci" not in json_content

    json_content = await aiottp_get_json(f"https://{generated_data.server_name}/.well-known/matrix/server", ssl_context)
    if value_file_has("synapse.enabled", True):
        assert "m.server" in json_content
    else:
        assert json_content == {}

    json_content = await aiottp_get_json(
        f"https://{generated_data.server_name}/.well-known/matrix/support", ssl_context
    )
    assert json_content == {}

    json_content = await aiottp_get_json(
        f"https://{generated_data.server_name}/.well-known/element/element.json", ssl_context
    )
    assert json_content == {}


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.asyncio_cooperative
async def test_root_url_redirects(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("well-known")

    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            "https://127.0.0.1",
            headers={"Host": generated_data.server_name},
            server_hostname=generated_data.server_name,
            allow_redirects=False,
        ) as response,
    ):
        assert response.status == 301
        assert "Location" in response.headers
        assert response.headers["Location"] == "https://redirect.localhost/path"
