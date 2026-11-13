# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

import pytest
import semver

from .fixtures import ESSData
from .lib.utils import aiohttp_client, aiohttp_get_json, value_file_has


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.asyncio_cooperative
async def test_well_known_files_can_be_accessed(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("well-known")

    json_content = await aiohttp_get_json(
        f"https://{generated_data.server_name}/.well-known/matrix/client", {}, ssl_context
    )
    if value_file_has("synapse.enabled", True):
        assert "m.homeserver" in json_content
    if value_file_has("matrixRTC.enabled", True):
        assert json_content["org.matrix.msc4143.rtc_foci"] == [
            {"type": "livekit", "livekit_service_url": f"https://mrtc.{generated_data.server_name}"}
        ]
    else:
        assert "org.matrix.msc4143.rtc_foci" not in json_content

    json_content = await aiohttp_get_json(
        f"https://{generated_data.server_name}/.well-known/matrix/server", {}, ssl_context
    )
    if value_file_has("synapse.enabled", True):
        assert "m.server" in json_content
    else:
        assert json_content == {}

    json_content = await aiohttp_get_json(
        f"https://{generated_data.server_name}/.well-known/matrix/support", {}, ssl_context
    )
    assert json_content == {}


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.skipif(
    not value_file_has("wellKnownDelegation.baseDomainRedirect", {}),
    reason="WellKnownDelegation base domain redirect is disabled",
)
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


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.asyncio_cooperative
async def test_delete_405(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("well-known")

    # We don't check which step we're on as Helm won't wait for the Pods from the old ReplicaSet to go away
    # We rely on the non-upgrade test working
    has_matrix_response = not (
        semver.Version.is_valid(os.environ.get("MATRIX_TEST_FROM_REF", ""))
        and semver.VersionInfo.parse(os.environ.get("MATRIX_TEST_FROM_REF", "")).compare("26.11.1") == 0
    )

    for path in [
        ".well-known/matrix/client",
        ".well-known/matrix/server",
        ".well-known/matrix/support",
    ]:
        async with (
            aiohttp_client(ssl_context) as client,
            client.delete(
                f"https://127.0.0.1/{path}",
                headers={"Host": generated_data.server_name},
                server_hostname=generated_data.server_name,
                raise_for_status=False,
            ) as response,
        ):
            assert response.status == 405
            if has_matrix_response:
                assert response.headers["content-type"] == "application/json"
                assert await response.json() == {
                    "errcode": "M_UNRECOGNIZED",
                    "error": "This endpoint is implemented, but the method is not supported.",
                }

        async with (
            aiohttp_client(ssl_context) as client,
            client.post(
                f"https://127.0.0.1/{path}",
                data={},
                headers={"Host": generated_data.server_name},
                server_hostname=generated_data.server_name,
                raise_for_status=False,
            ) as response,
        ):
            assert response.status == 405
            if has_matrix_response:
                assert response.headers["content-type"] == "application/json"
                assert await response.json() == {
                    "errcode": "M_UNRECOGNIZED",
                    "error": "This endpoint is implemented, but the method is not supported.",
                }

        async with (
            aiohttp_client(ssl_context) as client,
            client.put(
                f"https://127.0.0.1/{path}",
                data={},
                headers={"Host": generated_data.server_name},
                server_hostname=generated_data.server_name,
                raise_for_status=False,
            ) as response,
        ):
            assert response.status == 405
            if has_matrix_response:
                assert response.headers["content-type"] == "application/json"
                assert await response.json() == {
                    "errcode": "M_UNRECOGNIZED",
                    "error": "This endpoint is implemented, but the method is not supported.",
                }
