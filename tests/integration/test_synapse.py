# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
from pathlib import Path

import pyhelm3
import pytest
from aiohttp.client_exceptions import ClientResponseError
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Pod

from .fixtures import ESSData, User
from .lib.helpers import deploy_with_values_patch, get_deployment_marker
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
@pytest.mark.parametrize("users", [(User(name="sliding-sync-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_simplified_sliding_sync_syncs(ingress_ready, ssl_context, users, generated_data: ESSData):
    await ingress_ready("synapse")

    access_token = users[0].access_token

    sync_result = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.simplified_msc3575/sync",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert "pos" in sync_result


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.asyncio_cooperative
async def test_routes_to_synapse_workers_correctly(
    ingress_ready, kube_client: AsyncClient, ssl_context, generated_data: ESSData
):
    await ingress_ready("synapse")

    main_backend = "main/main"
    if value_file_has("synapse.workers.sliding-sync.enabled", True):
        sliding_sync_backend = "sliding-sync/sliding-sync"
    else:
        sliding_sync_backend = main_backend

    if value_file_has("synapse.workers.synchrotron.enabled", True):
        synchrotron_backend = "synchrotron/synchrotron"
    else:
        synchrotron_backend = main_backend

    if value_file_has("synapse.workers.initial-synchrotron.enabled", True):
        initial_synchrotron_backend = "initial-synchrotron/initial-sync"
    else:
        initial_synchrotron_backend = synchrotron_backend

    # We don't care about any of these succeeding, only that the requests are made and HAProxy dispatches correctly
    # So no auth required and parameters can be made up
    paths_to_backends = {
        # initial-synchrotron
        "/_matrix/client/v3/initialSync": initial_synchrotron_backend,
        "/_matrix/client/v3/rooms/aroomid/initialSync": initial_synchrotron_backend,
        "/_matrix/client/v3/sync?full_state=true": initial_synchrotron_backend,
        "/_matrix/client/v3/sync": initial_synchrotron_backend,
        "/_matrix/client/v3/events": initial_synchrotron_backend,
        # synchrotron
        "/_matrix/client/v3/sync?since=recently": synchrotron_backend,
        "/_matrix/client/v3/events?from=recently": synchrotron_backend,
        # sliding-sync
        "/_matrix/client/unstable/org.matrix.simplified_msc3575/sync": sliding_sync_backend,
        # Would be client-reader but not configured in tests
        "/_matrix/client/versions": main_backend,
    }

    for path in paths_to_backends:
        try:
            await aiohttp_get_json(f"https://synapse.{generated_data.server_name}{path}", ssl_context)
        except ClientResponseError as e:
            # We can't use pytest.raises as no exception (200) is valid
            assert e.status in [401, 405], f"{path} had an unexpected status. {e=}"  # noqa P1017

    http_log_lines = []
    async for haproxy_pod in kube_client.list(
        Pod, namespace=generated_data.ess_namespace, labels={"app.kubernetes.io/name": "haproxy"}
    ):
        assert haproxy_pod.metadata
        assert haproxy_pod.metadata.name
        assert haproxy_pod.metadata.namespace
        async for log_line in kube_client.log(haproxy_pod.metadata.name, namespace=haproxy_pod.metadata.namespace):
            if "HTTP/1.1" in log_line:
                http_log_lines.append(log_line)

    for path, backend in paths_to_backends.items():
        matching_lines = [line for line in http_log_lines if f"GET {path} HTTP/1.1" in line]

        assert len(matching_lines) > 0, f"Requests for {path} did not appear in the HAProxy logs"
        for matching_line in matching_lines:
            # During the upgrade tests these requests may NOSRV as Synapse processes are down
            # We eventually succeed, so just ignore the requests that were retried
            if " 503 " in matching_line and " synapse-main/<NOSRV> " in matching_line:
                continue

            # We know we end up here at least once as 2xx/401/405 won't match the above check
            assert f"synapse-http-in synapse-{backend}" in matching_line, f"{path} was routed unexpectedly"


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.parametrize("users", [(User(name="media-upload-unauth"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_synapse_media_upload_fetch_authenticated(
    cluster,
    ssl_context,
    users,
    generated_data: ESSData,
):
    user_access_token = users[0].access_token

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
        "synapse-media-repo-0" if value_file_has("synapse.workers.media-repository.enabled", True) else "synapse-main-0"
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


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
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


@pytest.mark.skipif(value_file_has("deploymentMarkers.enabled", False), reason="Deployment Markers not enabled")
@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", True), reason="MAS is deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", True), reason="Syn2Mas is being run")
@pytest.mark.asyncio_cooperative
async def test_synapse_service_marker_legacy_auth(
    kube_client, helm_client: pyhelm3.Client, ingress_ready, generated_data: ESSData, ssl_context
):
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "legacy_auth"
    revision, error = await deploy_with_values_patch(
        generated_data,
        helm_client,
        {"matrixAuthenticationService": {"enabled": True, "ingress": {"host": "account.{{ $.Values.serverName }}"}}},
        timeout="15s",
    )
    assert error is not None
    assert revision.description
    assert revision.status == pyhelm3.ReleaseRevisionStatus.FAILED
    assert "pre-upgrade hooks failed" in revision.description
    # Assert that MAS is not enabled
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
        assert "If-Match" not in response.headers["Access-Control-Allow-Headers"], (
            "Response headers should not contain If-Match with MAS disabled"
        )
