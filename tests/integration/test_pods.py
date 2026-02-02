# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from lightkube import AsyncClient
from lightkube import operators as op
from lightkube.resources.core_v1 import Pod

from .fixtures.data import ESSData


@pytest.mark.asyncio_cooperative
async def test_pods_run_as_gid_0(
    kube_client: AsyncClient,
    generated_data: ESSData,
    matrix_stack,
):
    async for pod in kube_client.list(
        Pod, namespace=generated_data.ess_namespace, labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])}
    ):
        assert pod.spec
        assert pod.spec.securityContext
        assert pod.metadata
        assert pod.spec.securityContext.runAsGroup == 0, f"{pod.metadata.name} is running with GID != 0"
