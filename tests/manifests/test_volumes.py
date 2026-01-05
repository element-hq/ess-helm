# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import deepfreeze

from . import (
    DeployableDetails,
    PropertyType,
    secret_values_files_to_test,
    values_files_to_test,
)
from .utils import iterate_deployables_workload_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_emptyDirs_are_memory(templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "Job", "StatefulSet"]:
            continue

        for volume in template["spec"]["template"]["spec"].get("volumes", []):
            if "emptyDir" not in volume:
                continue

            assert "medium" in volume["emptyDir"], (
                f"{template_id(template)} has emptyDir {volume['name']} but doesn't set the medium"
            )
            assert volume["emptyDir"]["medium"] == "Memory", (
                f"{template_id(template)} has emptyDir {volume['name']} that isn't Memory backed"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_extra_volumes(values, make_templates):
    extra_volumes = deepfreeze(
        [
            {
                "name": "extra-volume",
                "emptyDir": {},
            },
        ]
    )
    extra_volumes_hooks = deepfreeze(
        [
            {
                "name": "extra-volume-context-hook",
                "mountContext": "hook",
                "emptyDir": {},
            },
        ]
    )

    extra_volumes_runtime = deepfreeze(
        [
            {
                "name": "extra-volume-context-runtime",
                "mountContext": "runtime",
                "emptyDir": {},
            },
        ]
    )

    def set_extra_volumes(deployable_details: DeployableDetails):
        if deployable_details.has_mount_context:
            deployable_details.set_helm_values(
                values,
                PropertyType.Volumes,
                extra_volumes + extra_volumes_hooks + extra_volumes_runtime,
            )
        else:
            deployable_details.set_helm_values(
                values,
                PropertyType.Volumes,
                extra_volumes,
            )

    template_id_to_pod_volumes = {}
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_volumes = deepfreeze(template["spec"]["template"]["spec"].get("volumes", []))
            template_id_to_pod_volumes[template_id(template)] = pod_volumes

    iterate_deployables_workload_parts(set_extra_volumes)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_volumes = deepfreeze(template["spec"]["template"]["spec"]["volumes"])
            if template_to_deployable_details(template).has_mount_context:
                if template["metadata"].get("annotations", {}).get("helm.sh/hook-weight"):
                    assert set(pod_volumes) - set(template_id_to_pod_volumes[f"{template_id(template)}"]) == set(
                        (extra_volumes_hooks[0].delete("mountContext"),) + extra_volumes
                    ), f"Pod container {template_id(template)} volume mounts {pod_volumes}"
                else:
                    assert set(pod_volumes) - set(template_id_to_pod_volumes[f"{template_id(template)}"]) == set(
                        (extra_volumes_runtime[0].delete("mountContext"),) + extra_volumes
                    ), f"Pod container {template_id(template)} volume mounts {pod_volumes}"
            else:
                assert "volumes" in template["spec"]["template"]["spec"], (
                    f"Pod volumes unexpectedly absent for {template_id(template)}"
                )

                assert set(pod_volumes) - set(template_id_to_pod_volumes[template_id(template)]) == set(
                    extra_volumes
                ), f"Pod volumes {pod_volumes} is missing expected extra volume"
