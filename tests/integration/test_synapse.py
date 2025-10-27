# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import hashlib
import uuid
from pathlib import Path

import aiohttp
import pyhelm3
import pytest
from lightkube import AsyncClient

from .fixtures import ESSData, User
from .lib.helpers import deploy_with_values_patch, get_deployment_marker
from .lib.synapse import assert_downloaded_content, download_media, upload_media
from .lib.utils import (
    KubeCtl,
    aiohttp_client,
    aiohttp_get_json,
    aiohttp_post_json,
    forward_matching_logs,
    stream_logs_from_pods_matching_labels,
    value_file_has,
)


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.asyncio_cooperative
async def test_synapse_exposes_chart_version_edition(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
    helm_client: pyhelm3.Client,
):
    await ingress_ready("synapse")

    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    metadata = await revision.chart_metadata()

    json_content = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_synapse/ess/version", {}, ssl_context
    )
    assert "edition" in json_content
    assert json_content["edition"] == "community"

    assert "version" in json_content
    assert json_content["version"] == metadata.version


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.asyncio_cooperative
async def test_synapse_can_access_client_api(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
    helm_client: pyhelm3.Client,
):
    await ingress_ready("synapse")

    json_content = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/versions", {}, ssl_context
    )
    assert "unstable_features" in json_content

    supports_qr_code_login = value_file_has("matrixAuthenticationService.enabled", True)
    assert supports_qr_code_login == json_content["unstable_features"]["org.matrix.msc4108"]

    # Push notifications for encrypted messages
    assert json_content["unstable_features"]["org.matrix.msc4028"]


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
@pytest.mark.skipif(
    value_file_has("matrixAuthenticationService.syn2mas.enabled", True),
    reason="Syn2Mas is being run and so HAProxy logs may disappear as it restarts",
)
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

    all_haproxy_logs: asyncio.Queue = asyncio.Queue()
    haproxy_logs_streaming_task = asyncio.create_task(
        stream_logs_from_pods_matching_labels(
            kube_client, generated_data.ess_namespace, {"app.kubernetes.io/name": "haproxy"}, all_haproxy_logs
        )
    )

    async def make_request_and_assert_backend_used(path, backend, ssl_context, logs_matching_path: asyncio.Queue):
        attempt_ids = []
        matching_lines = []
        attempts = 0
        while attempts < 30:
            attempt_id = str(uuid.uuid4())
            attempt_ids.append(attempt_id)
            try:
                await aiohttp_get_json(
                    f"https://synapse.{generated_data.server_name}{path}", {"User-agent": attempt_id}, ssl_context
                )
            except aiohttp.ClientResponseError as e:
                # We can't use pytest.raises as no exception (200) is valid
                assert e.status in [401, 405], f"{path} had an unexpected status. {e=}"  # noqa P1017

            while True:
                # Given we've made at least one request, we know there should be something here and we can block for it
                # However sometimes it appears that logs aren't emitted from HAProxy so don't block indefinitely
                try:
                    log_line = await asyncio.wait_for(logs_matching_path.get(), timeout=1.0)
                except TimeoutError:
                    print(f"No HAProxy logs relating to {path} emitted after 1s. Retrying")
                    break

                # Save off lines from any run we encounter, not just the current one
                if any([id in log_line for id in attempt_ids]):
                    matching_lines.append(log_line)

                if attempt_id in log_line:
                    if f"synapse-http-in synapse-{backend}" in log_line:
                        return
                    else:
                        print(f"Request for {path} routed elsewhere: {log_line}")

            attempts += 1
            await asyncio.sleep(1)
        raise AssertionError(
            f"Requests to {path} did not end up at synapse-{backend} over 30s/attempts. "
            f"Log lines={'\n*'.join(matching_lines)}"
        )

    async with asyncio.TaskGroup() as task_group:
        path_matchers_and_log_queues = []
        for path, backend in paths_to_backends.items():
            logs_matching_path: asyncio.Queue = asyncio.Queue()
            path_matchers_and_log_queues.append((lambda log_line, path=path: path in log_line, logs_matching_path))
            task_group.create_task(make_request_and_assert_backend_used(path, backend, ssl_context, logs_matching_path))

        forward_matching_logs_task = asyncio.create_task(
            forward_matching_logs(all_haproxy_logs, path_matchers_and_log_queues)
        )

    haproxy_logs_streaming_task.cancel()
    forward_matching_logs_task.cancel()


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
