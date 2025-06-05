# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import aiohttp
import pyhelm3
import pytest
from lightkube import AsyncClient

from .fixtures import ESSData
from .lib.helpers import deploy_with_values_patch, get_deployment_marker
from .lib.utils import aiohttp_get_json, aiohttp_post_json, value_file_has
from .test_matrix_authentication_service import test_matrix_authentication_service_graphql_endpoint


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", False), reason="Syn2Mas not deployed")
@pytest.mark.parametrize("users", [("syn2mas-user",)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_run_syn2mas_upgrade(
    helm_client: pyhelm3.Client,
    kube_client: AsyncClient,
    users,
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    access_token = users[0]
    await ingress_ready("synapse")
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "legacy_auth"
    # After the base chart is setup, we enable MAS to run the syn2mas dry run job
    revision, error = await deploy_with_values_patch(
        generated_data, helm_client, {"matrixAuthenticationService": {"enabled": True}}
    )
    assert error is None
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED
    # We should still be able to reach synapse ingress
    await ingress_ready("synapse")

    # Auth metadata endpoint should not be reachable
    with pytest.raises(aiohttp.ClientResponseError):
        await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.msc2965/auth_metadata",
            ssl_context,
        )

    # Syn2Mas is running in dryRun mode, so the state has not changed yet
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "legacy_auth"

    # MAS should be reachable through its ingress
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    # After the base chart is setup, we enable MAS to run the syn2mas actual migration
    revision, error = await deploy_with_values_patch(
        generated_data, helm_client, {"matrixAuthenticationService": {"syn2mas": {"dryRun": False}}}
    )
    assert error is None
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED

    # Syn2Mas is running in migrate mode, so the state must have changed
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "syn2mas_migrated"

    # Auth metadata endpoint should be reachable
    response = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.msc2965/auth_metadata",
        ssl_context,
    )
    assert "issuer" in response

    # MAS should be reachable through its ingress
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    # The Synapse-issued tokens should have been migrated
    sync_result = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.simplified_msc3575/sync",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert "pos" in sync_result, (
        "The sync result failed, meaning the Synapse-issued tokens have probably not been migrated"
    )
    revision, error = await deploy_with_values_patch(
        generated_data, helm_client, {"matrixAuthenticationService": {"syn2mas": {"enabled": False}}}
    )
    assert error is None
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED

    # MAS should be available
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    # The marker should now show delegated_auth
    assert await get_deployment_marker(kube_client, generated_data, "MATRIX_STACK_MSC3861") == "delegated_auth"
    revision, error = await deploy_with_values_patch(
        generated_data, helm_client, {"matrixAuthenticationService": {"syn2mas": {"enabled": True}}}, timeout="15s"
    )
    assert error is not None
    assert revision.status == pyhelm3.ReleaseRevisionStatus.FAILED
    assert "pre-upgrade hooks failed" in revision.description
    # Assert that MAS still works
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    # Auth metadata endpoint should be reachable
    response = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.msc2965/auth_metadata",
        ssl_context,
    )
    assert "issuer" in response
