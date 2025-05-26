# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
from base64 import b64decode
from pathlib import Path

import pytest
from lightkube.resources.core_v1 import Secret

from .fixtures import ESSData
from .lib.synapse import assert_downloaded_content, download_media, upload_media
from .lib.utils import KubeCtl, aiohttp_client, aiohttp_get_json, aiohttp_post_json, value_file_has


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.asyncio_cooperative
async def test_synapse_can_access_client_api(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("synapse")

    json_content = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/versions", ssl_context
    )
    assert "unstable_features" in json_content

    supports_qr_code_login = value_file_has("matrixAuthenticationService.enabled", True)
    assert supports_qr_code_login == json_content["unstable_features"]["org.matrix.msc4108"]


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.parametrize("users", [("sliding-sync-user",)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_simplified_sliding_sync_syncs(ssl_context, users, generated_data: ESSData):
    access_token = users[0]

    sync_result = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.simplified_msc3575/sync",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert "pos" in sync_result


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.parametrize("users", [("media-upload-unauth",)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_synapse_media_upload_fetch_authenticated(
    cluster,
    ssl_context,
    users,
    generated_data: ESSData,
):
    user_access_token = users[0]

    filepath = Path(__file__).parent.resolve() / Path("artifacts/files/minimal.png")
    with open(filepath, "rb") as file:
        source_sha256 = hashlib.file_digest(file, "sha256").hexdigest()

    content_upload_json = await upload_media(
        synapse_fqdn=f"synapse.{generated_data.server_name}",
        user_access_token=user_access_token,
        file_path=filepath,
        ssl_context=ssl_context,
    )

    content_download_sha256 = await download_media(
        server_name=generated_data.server_name,
        user_access_token=user_access_token,
        synapse_fqdn=f"synapse.{generated_data.server_name}",
        content_upload_json=content_upload_json,
        ssl_context=ssl_context,
    )

    media_pod_suffix = (
        "synapse-media-repository-0"
        if value_file_has("synapse.workers.media-repository.enabled", True)
        else "synapse-main-0"
    )
    media_pod = f"{generated_data.release_name}-{media_pod_suffix}"

    await assert_downloaded_content(
        KubeCtl(cluster),
        media_pod,
        generated_data.ess_namespace,
        source_sha256,
        content_upload_json["content_uri"].replace(f"mxc://{generated_data.server_name}/", ""),
        content_download_sha256,
    )


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="MAS not deployed")
@pytest.mark.asyncio_cooperative
async def test_rendezvous_cors_headers_are_only_set_with_mas(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("synapse")
    async with (
        aiohttp_client(ssl_context) as client,
        client.options(
            f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.msc4108/rendezvous",
        ) as response,
    ):
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

        assert "Access-Control-Allow-Headers" in response.headers
        supports_qr_code_login = value_file_has("matrixAuthenticationService.enabled", True)
        assert ("If-Match" in response.headers["Access-Control-Allow-Headers"]) == supports_qr_code_login

        assert "Access-Control-Expose-Headers" in response.headers
        assert "Synapse-Trace-Id" in response.headers["Access-Control-Expose-Headers"]
        assert "Server" in response.headers["Access-Control-Expose-Headers"]
        assert ("ETag" in response.headers["Access-Control-Expose-Headers"]) == supports_qr_code_login


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", True), reason="MAS is deployed")
@pytest.mark.asyncio_cooperative
async def test_synapse_service_marker_legacy_auth(kube_client, generated_data: ESSData, ssl_context):
    secret = await kube_client.get(
        Secret,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert secret.data.get("MATRIX_STACK_MSC3861") is not None
    assert b64decode(secret.data.get("MATRIX_STACK_MSC3861")) == b"legacy_auth"
