# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from base64 import b64decode

import pytest
from lightkube.resources.core_v1 import Secret

from .fixtures import ESSData
from .lib.utils import aiohttp_post_json, value_file_has


@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
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
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_marker_delegated_auth(kube_client, generated_data: ESSData, ssl_context):
    secret = await kube_client.get(
        Secret,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert secret.data.get("MATRIX_STACK_MSC3861") is not None
    assert b64decode(secret.data.get("MATRIX_STACK_MSC3861")) == b"delegated_auth"
