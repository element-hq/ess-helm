# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import deepfreeze

from . import (
    DeployableDetails,
    PropertyType,
    values_files_to_test,
)
from .utils import iterate_deployables_workload_parts, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_extra_volumes(values, make_templates, release_name):
    def extra_volumes(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}",
                    "configMap": {
                        "name": "config-{{ $.Release.Name }}",
                    },
                },
            ]
        )

    def extra_volumes_hooks(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}-context-hook",
                    "mountContext": "hook",
                    "configMap": {
                        "name": "config-{{ $.Release.Name }}",
                    },
                },
            ]
        )

    def extra_volumes_runtime(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}-context-runtime",
                    "mountContext": "runtime",
                    "configMap": {
                        "name": "config-{{ $.Release.Name }}",
                    },
                },
            ]
        )

    def set_extra_volumes(deployable_details: DeployableDetails):
        if deployable_details.has_mount_context:
            deployable_details.set_helm_values(
                values,
                PropertyType.Volumes,
                extra_volumes(deployable_details)
                + extra_volumes_hooks(deployable_details)
                + extra_volumes_runtime(deployable_details),
            )
        else:
            deployable_details.set_helm_values(
                values,
                PropertyType.Volumes,
                extra_volumes(deployable_details),
            )

    def get_expected_volumes_from_values(deployable_details: DeployableDetails, with_hooks: bool):
        volumes = deepfreeze(deployable_details.get_helm_values(values, PropertyType.Volumes, default_value=None))
        expected_volumes = []
        for v in volumes:
            new_volume = v
            if new_volume.get("mountContext"):
                if with_hooks is None:
                    raise RuntimeError(
                        f"{deployable_details.name} : Encountered a volume with mountContext, "
                        f"but we expected none : {v}"
                    )
                elif (
                    v.get("mountContext") == "hook"
                    and with_hooks
                    or v.get("mountContext") == "runtime"
                    and not with_hooks
                ):
                    new_volume = new_volume.delete("mountContext")
                else:
                    continue
            new_volume = new_volume.set(
                "configMap",
                v["configMap"].set("name", v["configMap"]["name"].replace("{{ $.Release.Name }}", release_name)),
            )
            expected_volumes.append(new_volume)
        return expected_volumes

    template_id_to_pod_volumes = {}
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_volumes = deepfreeze(pod_template_details.pod_template["spec"].get("volumes", []))
        template_id_to_pod_volumes[pod_template_details.manifest_id] = pod_volumes

    iterate_deployables_workload_parts(set_extra_volumes)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        assert "volumes" in pod_template_details.pod_template["spec"], (
            f"Pod volumes unexpectedly absent for {pod_template_details.manifest_id}"
        )
        pod_volumes = deepfreeze(pod_template_details.pod_template["spec"]["volumes"])
        deployable_details = pod_template_details.deployable_details()
        if deployable_details.has_mount_context:
            if pod_template_details.manifest["metadata"].get("annotations", {}).get("helm.sh/hook-weight"):
                assert set(pod_volumes) - set(template_id_to_pod_volumes[pod_template_details.manifest_id]) == set(
                    get_expected_volumes_from_values(deployable_details, with_hooks=True)
                ), f"Pod container {pod_template_details.manifest_id} volume mounts {pod_volumes}"
            else:
                assert set(pod_volumes) - set(template_id_to_pod_volumes[pod_template_details.manifest_id]) == set(
                    get_expected_volumes_from_values(deployable_details, with_hooks=False)
                ), f"Pod container {pod_template_details.manifest_id} volume mounts {pod_volumes}"
        else:
            assert "volumes" in pod_template_details.pod_template["spec"], (
                f"Pod volumes unexpectedly absent for {pod_template_details.manifest_id}"
            )

            assert set(pod_volumes) - set(template_id_to_pod_volumes[pod_template_details.manifest_id]) == set(
                get_expected_volumes_from_values(deployable_details, with_hooks=None)
            ), f"Pod volumes {pod_volumes} is missing expected extra volume"
