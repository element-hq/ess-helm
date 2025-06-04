# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pyhelm3
import pytest
from lightkube.resources.core_v1 import ConfigMap

from .fixtures import ESSData
from .lib.utils import aiohttp_post_json, value_file_has


@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", True), reason="Syn2Mas is being run")
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("matrix-authentication-service")
    mas_query = {
        "query": "query UserByUsername($username: String!) { userByUsername(username: $username) { id lockedAt } }",
        "variables": {"username": "test"},
    }
    json_content = await aiohttp_post_json(
        f"https://mas.{generated_data.server_name}/graphql", mas_query, {}, ssl_context
    )
    assert "errors" not in json_content or len(json_content["errors"]) == 0, json_content
    # When not authenticated, the userByUsername will return an empty result whatever the username queried
    assert json_content["data"] == {"userByUsername": None}


@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", True), reason="Syn2Mas is being run")
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_marker_delegated_auth(
    kube_client, helm_client: pyhelm3.Client, ingress_ready, generated_data: ESSData, ssl_context
):
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert configmap.data.get("MATRIX_STACK_MSC3861") == "delegated_auth"

    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    values = await revision.values()
    values.setdefault("matrixAuthenticationService", {})["enabled"] = False
    chart = await helm_client.get_chart("charts/matrix-stack")
    with pytest.raises(pyhelm3.errors.Error):
        # Install or upgrade a release
        await helm_client.install_or_upgrade_release(
            generated_data.release_name,
            chart,
            values,
            namespace=generated_data.ess_namespace,
            atomic=False,
            timeout="15s",
            wait=True,
        )
    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.FAILED
    assert "pre-upgrade hooks failed" in revision.description
    # Assert that MAS still works
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)
