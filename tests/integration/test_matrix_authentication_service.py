# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pyhelm3
import pytest

from .fixtures import ESSData
from .lib.helpers import deploy_with_values_patch, get_deployment_marker
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


@pytest.mark.skipif(value_file_has("deploymentMarkers.enabled", False), reason="Deployment Markers not enabled")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", True), reason="Syn2Mas is being run")
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_marker_delegated_auth(
    kube_client, helm_client: pyhelm3.Client, ingress_ready, generated_data: ESSData, ssl_context
):
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "delegated_auth"

    revision, error = await deploy_with_values_patch(
        generated_data, helm_client, {"matrixAuthenticationService": {"enabled": False}}, timeout="15s"
    )
    assert error is not None
    assert revision.description
    assert revision.status == pyhelm3.ReleaseRevisionStatus.FAILED
    assert "pre-upgrade hooks failed" in revision.description
    # Assert that MAS still works
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)
