# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from .fixtures import ESSData, User
from .lib.utils import aiohttp_post_json, value_file_has


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="Well-Known Delegation not deployed")
@pytest.mark.parametrize("users", [(User(name="matrix-rtc-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_element_call_livekit_jwt(ingress_ready, users, generated_data: ESSData, ssl_context):
    await ingress_ready("synapse")
    access_token = users[0].access_token

    openid_token = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/user/@matrix-rtc-user:{generated_data.server_name}/openid/request_token",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    livekit_jwt_payload = {
        "openid_token": {
            "access_token": openid_token["access_token"],
            "matrix_server_name": generated_data.server_name,
        },
        "room": f"!blah:{generated_data.server_name}",
        "device_id": "something",
    }

    await ingress_ready("matrix-rtc")
    await ingress_ready("well-known")
    livekit_jwt = await aiohttp_post_json(
        f"https://mrtc.{generated_data.server_name}/sfu/get",
        livekit_jwt_payload,
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert livekit_jwt["url"] == f"wss://mrtc.{generated_data.server_name}"
    assert "jwt" in livekit_jwt
