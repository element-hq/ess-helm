# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

import pyhelm3
import pytest
from lightkube import AsyncClient
from lightkube.resources.core_v1 import ConfigMap

from .fixtures import ESSData
from .lib.utils import aiohttp_post_json, value_file_has
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
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert configmap.data.get("MATRIX_STACK_MSC3861") == "legacy_auth"

    # After the base chart is setup, we enable MAS to run the syn2mas dry run job
    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    values = await revision.values()
    values["matrixAuthenticationService"]["enabled"] = True
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED
    # We should still be able to reach synapse ingress
    await ingress_ready("synapse")

    # Syn2Mas is running in dryRun mode, so the state has not changed yet
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert configmap.data.get("MATRIX_STACK_MSC3861") == "legacy_auth"

    # We then run the migration
    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    values = await revision.values()
    values["matrixAuthenticationService"]["syn2mas"]["dryRun"] = False
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED

    # Syn2Mas is running in migrate mode, so the state must have changed
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert configmap.data.get("MATRIX_STACK_MSC3861") == "syn2mas_migrated"

    # We should still be able to reach synapse ingress
    await ingress_ready("synapse")
    # MAS should be available
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    sync_result = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.simplified_msc3575/sync",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert "pos" in sync_result

    # We then disable syn2mas to complete the migration
    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    values = await revision.values()
    values["matrixAuthenticationService"]["syn2mas"]["enabled"] = False
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert error is None
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED

    # We should still be able to reach synapse ingress
    await ingress_ready("synapse")
    # MAS should be available
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    # The marker should now show delegated_auth
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    assert configmap.data.get("MATRIX_STACK_MSC3861") == "delegated_auth"
