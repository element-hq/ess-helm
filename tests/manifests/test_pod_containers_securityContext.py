# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_containers_unprivileged_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            securityContext = container["securityContext"]

            assert "privileged" in securityContext, f"{id} doesn't set privileged in its securityContext"
            assert not securityContext["privileged"], (
                f"{id} doesn't set privileged=false in its securityContext by default"
            )

            assert "allowPrivilegeEscalation" in securityContext, (
                f"{id} doesn't set allowPrivilegeEscalation in its securityContext"
            )
            assert not securityContext["allowPrivilegeEscalation"], (
                f"{id} doesn't set allowPrivilegeEscalation=false in its securityContext by default"
            )

            assert "readOnlyRootFilesystem" in securityContext, (
                f"{id} doesn't set readOnlyRootFilesystem in its securityContext"
            )
            assert securityContext["readOnlyRootFilesystem"], (
                f"{id} doesn't set readOnlyRootFilesystem=true in its securityContext by default"
            )

            assert "capabilities" in securityContext, f"{id} doesn't set capabilities in its securityContext"
            assert securityContext["capabilities"] == {"drop": ("ALL",)}, (
                f"{id} doesn't drop all capabilities in its securityContext by default"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_containers_can_be_made_more_privileged(values, make_templates):
    iterate_deployables_workload_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values,
            PropertyType.ContainersSecurityContext,
            {
                "privileged": True,
                "allowPrivilegeEscalation": True,
                "readOnlyRootFilesystem": False,
                "capabilities": {"add": ["NET_ADMIN"], "drop": []},
            },
        ),
    )
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            securityContext = container["securityContext"]

            assert securityContext["privileged"], f"{id} doesn't set privileged=true in its securityContext"
            assert securityContext["allowPrivilegeEscalation"], (
                f"{id} doesn't set allowPrivilegeEscalation=true in its securityContext"
            )
            assert not securityContext["readOnlyRootFilesystem"], (
                f"{id} doesn't set readOnlyRootFilesystem=false in its securityContext"
            )
            assert securityContext["capabilities"] == {"add": ("NET_ADMIN",), "drop": ()}, (
                f"{id} doesn't respect the configured capabilities in its securityContext"
            )
