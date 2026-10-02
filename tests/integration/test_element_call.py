# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os
import ssl
from urllib.parse import quote

import aiohttp
import pytest
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Service

from .fixtures import ESSData, User
from .lib.utils import (
    aiohttp_get_json,
    aiohttp_post_json,
    aiohttp_put_json,
    async_retry_with_timeout,
    value_file_has,
)

# Synapse proxies these endpoints to the MatrixRTC Authorisation Service (MSC4512)
PROXIED_MATRIX_RTC_PATH = "/_matrix/client/unstable/io.element.msc4195/rtc/livekit"

# The upgrade tests first deploy the latest release, which doesn't proxy the Matrix RTC endpoints yet
# TODO: set to the most recent release before merging
LAST_RELEASE_WITHOUT_RTC_PROXY = "26.9.4"
UPGRADE_TEST_STARTS_FROM_IT = os.environ.get("MATRIX_TEST_FROM_REF", "") == LAST_RELEASE_WITHOUT_RTC_PROXY
RUNS_RELEASE_WITHOUT_RTC_PROXY = UPGRADE_TEST_STARTS_FROM_IT and os.environ.get("PYTEST_CI_FIRST_STEP", "") == "1"


def user_id(generated_data: ESSData, user: User) -> str:
    return f"@{user.name}:{generated_data.server_name}"


def matrix_rtc_member(generated_data: ESSData, user: User) -> dict:
    return {
        "id": "pytest-member",
        "claimed_user_id": user_id(generated_data, user),
        "claimed_device_id": "PYTESTDEVICE",
    }


async def openid_token(generated_data: ESSData, user: User, ssl_context) -> dict:
    token = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/user/"
        f"{quote(user_id(generated_data, user), safe='')}/openid/request_token",
        {},
        {"Authorization": f"Bearer {user.access_token}"},
        ssl_context,
    )
    return {"access_token": token["access_token"], "matrix_server_name": generated_data.server_name}


def leave_event_url(generated_data: ESSData, user: User, room_id: str) -> str:
    return (
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/state/"
        f"org.matrix.msc3401.call.member/{quote(user_id(generated_data, user), safe='')}"
    )


async def schedule_delayed_leave(generated_data: ESSData, user: User, room_id: str, delay_ms: int, ssl_context) -> str:
    """Schedules a delayed MatrixRTC leave event (MSC4140) for the user and returns its delay ID."""
    # TODO: schedule it with the dedicated MSC4140 endpoint once the chart's Synapse has it (element-hq/synapse#19354):
    # PUT /_matrix/client/unstable/org.matrix.msc4140/rooms/{roomId}/delayed_event/{eventType}/{txnId}
    delayed_event = await aiohttp_put_json(
        f"{leave_event_url(generated_data, user, room_id)}?org.matrix.msc4140.delay={delay_ms}",
        {},
        {"Authorization": f"Bearer {user.access_token}"},
        ssl_context,
    )
    return delayed_event["delay_id"]


async def wait_for_leave_event(generated_data: ESSData, user: User, room_id: str, ssl_context) -> dict:
    async def _leave_event():
        return await aiohttp_get_json(
            leave_event_url(generated_data, user, room_id),
            {"Authorization": f"Bearer {user.access_token}"},
            ssl_context,
        )

    return await async_retry_with_timeout(
        _leave_event,
        max_retries=60,
        should_retry=lambda e: isinstance(e, aiohttp.ClientResponseError) and e.status == 404,
    )


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


# Clients delegate their delayed leave event (MSC4140) to the authorisation service when they request a token
@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="Well-Known Delegation not deployed")
@pytest.mark.parametrize("users", [(User(name="matrix-rtc-get-token-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_get_token_with_delegated_delayed_leave(
    ingress_ready, users, generated_data: ESSData, ssl_context
):
    await ingress_ready("synapse")
    await ingress_ready("matrix-rtc")
    await ingress_ready("well-known")

    room = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/createRoom",
        {},
        {"Authorization": f"Bearer {users[0].access_token}"},
        ssl_context,
    )
    # The leave event is scheduled far enough in the future to not be sent by Synapse during the test
    delay_id = await schedule_delayed_leave(generated_data, users[0], room["room_id"], 3600000, ssl_context)

    livekit_jwt = await aiohttp_post_json(
        f"https://mrtc.{generated_data.server_name}/get_token",
        {
            "room_id": room["room_id"],
            "slot_id": "m.call#ROOM",
            "openid_token": await openid_token(generated_data, users[0], ssl_context),
            "member": matrix_rtc_member(generated_data, users[0]),
            "delay_id": delay_id,
            "delay_timeout": 2000,
        },
        {},
        ssl_context,
    )
    assert livekit_jwt["url"] == f"wss://mrtc.{generated_data.server_name}"
    assert "jwt" in livekit_jwt

    # The user never connects to the SFU. After `delay_timeout` the authorisation service gives up waiting
    # and sends the leave event on behalf of the user
    assert await wait_for_leave_event(generated_data, users[0], room["room_id"], ssl_context) == {}


def proxied_matrix_rtc_request(generated_data: ESSData, user: User, room_id: str) -> dict:
    return {
        "url": f"wss://mrtc.{generated_data.server_name}",
        "room_id": room_id,
        "slot_id": "m.call#ROOM",
        "member": matrix_rtc_member(generated_data, user),
    }


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(
    RUNS_RELEASE_WITHOUT_RTC_PROXY, reason=f"{LAST_RELEASE_WITHOUT_RTC_PROXY} doesn't proxy the Matrix RTC endpoints"
)
@pytest.mark.parametrize("users", [(User(name="matrix-rtc-proxied-token-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_get_token_through_synapse(ingress_ready, users, generated_data: ESSData, ssl_context):
    await ingress_ready("synapse")
    await ingress_ready("matrix-rtc")
    synapse = f"https://synapse.{generated_data.server_name}"
    headers = {"Authorization": f"Bearer {users[0].access_token}"}

    room = await aiohttp_post_json(f"{synapse}/_matrix/client/v3/createRoom", {}, headers, ssl_context)

    # Synapse authenticates the user and forwards the request to the authorisation service with its hs_token.
    # The authorisation service then checks with its as_token that the user is joined to the room (MSC4502)
    livekit_jwt = await aiohttp_post_json(
        f"{synapse}{PROXIED_MATRIX_RTC_PATH}/get_token",
        proxied_matrix_rtc_request(generated_data, users[0], room["room_id"]),
        headers,
        ssl_context,
    )
    assert "jwt" in livekit_jwt

    with pytest.raises(aiohttp.ClientResponseError) as not_joined:
        await aiohttp_post_json(
            f"{synapse}{PROXIED_MATRIX_RTC_PATH}/get_token",
            proxied_matrix_rtc_request(generated_data, users[0], f"!not-joined:{generated_data.server_name}"),
            headers,
            ssl_context,
        )
    assert not_joined.value.status == 403


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(
    RUNS_RELEASE_WITHOUT_RTC_PROXY, reason=f"{LAST_RELEASE_WITHOUT_RTC_PROXY} doesn't proxy the Matrix RTC endpoints"
)
@pytest.mark.parametrize("users", [(User(name="matrix-rtc-proxied-leave-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_delayed_leave_delegated_through_synapse(
    ingress_ready, users, generated_data: ESSData, ssl_context
):
    await ingress_ready("synapse")
    await ingress_ready("matrix-rtc")
    synapse = f"https://synapse.{generated_data.server_name}"
    headers = {"Authorization": f"Bearer {users[0].access_token}"}

    room = await aiohttp_post_json(f"{synapse}/_matrix/client/v3/createRoom", {}, headers, ssl_context)
    # The leave event is scheduled far enough in the future to not be sent by Synapse during the test
    delay_id = await schedule_delayed_leave(generated_data, users[0], room["room_id"], 3600000, ssl_context)

    # The user never connects to the SFU. After `delay_timeout` the authorisation service gives up waiting
    # and sends the leave event on behalf of the user, authenticating as an appservice asserting the user
    await aiohttp_post_json(
        f"{synapse}{PROXIED_MATRIX_RTC_PATH}/delegate_delayed_leave",
        proxied_matrix_rtc_request(generated_data, users[0], room["room_id"])
        | {"delay_id": delay_id, "delay_timeout": 2000},
        headers,
        ssl_context,
    )

    assert await wait_for_leave_event(generated_data, users[0], room["room_id"], ssl_context) == {}


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(
    not value_file_has("matrixRTC.sfu.exposedServices.turnTLS.enabled", True), reason="Matrix RTC TURN TLS not enabled"
)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_turn_tls(ingress_ready, generated_data: ESSData, ssl_context, kube_client: AsyncClient):
    await ingress_ready("matrix-rtc")

    # Get the turnTLS service to find the dynamically assigned NodePort
    turn_tls_service = await kube_client.get(
        Service, f"{generated_data.release_name}-matrix-rtc-sfu-turn-tls", namespace=generated_data.ess_namespace
    )

    # Find the NodePort from the service
    turn_tls_port = None
    if turn_tls_service.spec and turn_tls_service.spec.ports:
        for port in turn_tls_service.spec.ports:
            if port.name == "turn-tls-tcp":
                turn_tls_port = port.nodePort
                break

    assert turn_tls_port is not None, "Could not find turn-tls-tcp NodePort"
    assert 30016 <= turn_tls_port <= 30100, "NodePort should be in dynamic band range (according to our k3d conf)"

    async def _assert_tls_socket():
        reader, writer = await asyncio.open_connection(
            host="127.0.0.1",
            port=turn_tls_port,
            ssl=ssl_context,
            server_hostname=f"turn.{generated_data.server_name}",
            ssl_handshake_timeout=3.0,
        )

        # Send a test message
        writer.write(b"Hello TURN TLS")
        await writer.drain()

        # Close the connection
        writer.close()
        await writer.wait_closed()

    # The TLS socket can somewhat expect to fail while the stack boots
    await async_retry_with_timeout(
        _assert_tls_socket,
        should_retry=lambda e: type(e) in [ssl.SSLEOFError, ConnectionResetError],
    )


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(
    not value_file_has("matrixRTC.sfu.exposedServices.rtcTcp.enabled", True), reason="Matrix RTC TCP not enabled"
)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_rtc_tcp(ingress_ready, generated_data: ESSData, kube_client: AsyncClient):
    await ingress_ready("matrix-rtc")

    # Get the RTC TCP service to find the dynamically assigned NodePort
    rtc_tcp_service = await kube_client.get(
        Service, f"{generated_data.release_name}-matrix-rtc-sfu-tcp", namespace=generated_data.ess_namespace
    )

    # Find the NodePort from the service
    rtc_tcp_port = None
    if rtc_tcp_service.spec and rtc_tcp_service.spec.ports:
        for port in rtc_tcp_service.spec.ports:
            if port.name == "rtc-tcp":
                rtc_tcp_port = port.nodePort
                break

    assert rtc_tcp_port is not None, "Could not find rtc-tcp NodePort"
    assert 30016 <= rtc_tcp_port <= 30100, "NodePort should be in dynamic band range (according to our k3d conf)"

    async def _assert_tcp_socket():
        reader, writer = await asyncio.open_connection(
            host="127.0.0.1",
            port=rtc_tcp_port,
        )

        # Send a test message
        writer.write(b"Hello RTC TCP")
        await writer.drain()

        # Close the connection
        writer.close()
        await writer.wait_closed()

    # The TCP socket can fail while the stack boots
    await async_retry_with_timeout(
        _assert_tcp_socket,
        should_retry=lambda e: type(e) in [ConnectionResetError, ConnectionRefusedError],
    )


@pytest.mark.skipif(value_file_has("matrixRTC.enabled", False), reason="Matrix RTC not deployed")
@pytest.mark.skipif(
    not value_file_has("matrixRTC.sfu.exposedServices.rtcMuxedUdp.enabled", True), reason="Matrix RTC UDP not enabled"
)
@pytest.mark.asyncio_cooperative
async def test_matrix_rtc_rtc_udp_service_exists(ingress_ready, generated_data: ESSData, kube_client: AsyncClient):
    """Verify UDP service exists and has NodePort assigned (basic connectivity test)"""
    await ingress_ready("matrix-rtc")

    # Get the RTC UDP service
    rtc_udp_service = await kube_client.get(
        Service, f"{generated_data.release_name}-matrix-rtc-sfu-muxed-udp", namespace=generated_data.ess_namespace
    )

    # Verify it has a NodePort assigned
    rtc_udp_port = None
    if rtc_udp_service.spec and rtc_udp_service.spec.ports:
        for port in rtc_udp_service.spec.ports:
            if port.name == "rtc-muxed-udp":
                rtc_udp_port = port.nodePort
                break

    assert rtc_udp_port is not None, "UDP service should have NodePort assigned"
    assert 30016 <= rtc_udp_port <= 30100, "NodePort should be in dynamic band range (according to our k3d conf)"

    # Basic socket creation test
    class UDPTestProtocol(asyncio.DatagramProtocol):
        def connection_made(self, transport):
            self.transport = transport
            self.transport.sendto(b"UDP_TEST", ("127.0.0.1", rtc_udp_port))
            asyncio.get_event_loop().call_later(0.1, self.transport.close)

    async def _test_udp_socket():
        transport, _ = await asyncio.get_event_loop().create_datagram_endpoint(
            UDPTestProtocol, remote_addr=("127.0.0.1", rtc_udp_port)
        )
        await asyncio.sleep(0.2)  # Brief delay for socket operations

    await async_retry_with_timeout(_test_udp_socket, should_retry=lambda e: isinstance(e, OSError), timeout_seconds=5.0)
