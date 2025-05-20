# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

import pyhelm3
import pytest

from .fixtures import ESSData
from .lib.utils import aiohttp_post_json, value_file_has
from .test_matrix_authentication_service import test_matrix_authentication_service_graphql_endpoint


@pytest.mark.skipif(value_file_has("synapse.enabled", False), reason="Synapse not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.syn2mas.enabled", False), reason="Syn2Mas not deployed")
@pytest.mark.parametrize("users", [("syn2mas-user",)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_run_syn2mas_upgrade(
    helm_client: pyhelm3.Client,
    users,
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    access_token = users[0]
    await ingress_ready("synapse")
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
    # We then run the final migration
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

    # MAS should be available
    await test_matrix_authentication_service_graphql_endpoint(ingress_ready, generated_data, ssl_context)

    sync_result = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/unstable/org.matrix.simplified_msc3575/sync",
        {},
        {"Authorization": f"Bearer {access_token}"},
        ssl_context,
    )

    assert "pos" in sync_result
