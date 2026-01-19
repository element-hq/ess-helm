# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import socket

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


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(
    not value_file_has("matrixRTC.sfu.exposedServices.turnTLS.enabled", True), reason="Matrix RTC TURN TLS not enabled"
)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_turn_tls(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("matrix-rtc")
    # Open a TLS TCP Socket against the TURN server
    turn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    turn_socket.settimeout(5)
    turn_server_url = f"turn.{generated_data.server_name}", 31443
    turn_socket.connect(turn_server_url)
    print("Connected to TURN server without TLS")

    # Wrap the socket with TLS
    turn_tls_socket = ssl_context.wrap_socket(turn_socket, server_side=False, server_hostname=turn_server_url[0])

    # Now you can send/receive data over the TLS socket
    # For example, send a test message
    turn_tls_socket.sendall(b"Hello TURN TLS")

    # Close the connection
    turn_tls_socket.close()
