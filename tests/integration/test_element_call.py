# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import ssl

import pytest
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Service

from .fixtures import ESSData, User
from .lib.utils import aiohttp_post_json, async_retry_with_timeout, value_file_has


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
    assert 30086 <= turn_tls_port <= 30186, "NodePort should be in dynamic band range (according to our k3d conf)"

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
    assert 30086 <= rtc_tcp_port <= 30186, "NodePort should be in dynamic band range (according to our k3d conf)"

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
    assert 30086 <= rtc_udp_port <= 30186, "NodePort should be in dynamic band range (according to our k3d conf)"

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
