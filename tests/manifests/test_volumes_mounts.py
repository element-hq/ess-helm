# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest
from frozendict import deepfreeze

from . import (
    DeployableDetails,
    PropertyType,
    secret_values_files_to_test,
    values_files_to_test,
)
from .utils import (
    iterate_deployables_workload_parts,
    template_id,
    template_to_deployable_details,
    workload_spec_containers,
)


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_volumes_mounts_exists(release_name, templates, other_secrets, other_configmaps):
    configmaps_names = [t["metadata"]["name"] for t in templates if t["kind"] == "ConfigMap"] + [
        s["metadata"]["name"] for s in other_configmaps
    ]
    secrets_names = (
        [t["metadata"]["name"] for t in templates if t["kind"] == "Secret"]
        + [s["metadata"]["name"] for s in other_secrets]
        + [c["spec"]["secretName"] for c in [c for c in templates if c["kind"] == "Certificate"]]
    )
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            volumes_names = []
            for volume in template["spec"]["template"]["spec"].get("volumes", []):
                assert len(volume["name"]) <= 63, (
                    f"Volume name {volume['name']} is too long: {volume['name']} in {template_id(template)}"
                )
                assert volume["name"] not in volumes_names, (
                    f"Volume name {volume['name']} is listed multiple times in {template_id(template)}"
                )
                volumes_names.append(volume["name"])

                # Volumes could be dynamic in other ways, but including $.Release.Name is the most likely
                assert release_name not in volume["name"]

                if "secret" in volume:
                    assert volume["secret"]["secretName"] in secrets_names, (
                        f"Volume {volume['secret']['secretName']} not found in Secret names:"
                        f"{secrets_names} for {template_id(template)}"
                    )
                    assert re.match(
                        r"^((as)-\d+|(secret)-[a-f0-9]{12}|" + r"secret-(generated|turn-tls)|"
                        r")$",
                        volume["name"],
                    ), f"{template_id(template)} contains a Secret mounted with an unexpected name: {volume['name']}"
                if "configMap" in volume:
                    assert volume["configMap"]["name"] in configmaps_names, (
                        f"Volume {volume['configMap']['name']} not found in ConfigMap names:"
                        f"{configmaps_names} for {template_id(template)}"
                    )
                    assert re.match(
                        r"^("
                        r"(haproxy-|nginx-|plain)?(-syn-|-mas-|-)?config|"
                        r"(synapse|well-known)-haproxy|"
                        r"registration-templates|"
                        r"test-[\w-]+"
                        r")$",
                        volume["name"],
                    ), f"{template_id(template)} contains a ConfigMap mounted with an unexpected name: {volume['name']}"

            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                for volume_mount in container.get("volumeMounts", []):
                    assert volume_mount["name"] in volumes_names, (
                        f"Volume Mount {volume_mount['name']} not found in volume names: {volumes_names} "
                        f"for {template_id(template)}/{container['name']}"
                    )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_extra_volume_mounts(values, make_templates):
    def extra_volume_mounts(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}",
                    "mountPath": "/extra-volume",
                },
            ]
        )

    def extra_volume_mounts_hooks(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}-context-hook",
                    "mountContext": "hook",
                    "mountPath": "/extra-volume-context",
                },
            ]
        )

    def extra_volume_mounts_runtime(deployable_details: DeployableDetails):
        return deepfreeze(
            [
                {
                    "name": f"extra-volume-{deployable_details.name}-context-runtime",
                    "mountContext": "runtime",
                    "mountPath": "/extra-volume-context",
                },
            ]
        )

    def set_extra_volume_mounts(deployable_details: DeployableDetails):
        if deployable_details.has_mount_context:
            deployable_details.set_helm_values(
                values,
                PropertyType.VolumeMounts,
                extra_volume_mounts(deployable_details)
                + extra_volume_mounts_hooks(deployable_details)
                + extra_volume_mounts_runtime(deployable_details),
            )
        else:
            deployable_details.set_helm_values(
                values,
                PropertyType.VolumeMounts,
                extra_volume_mounts(deployable_details),
            )

    def get_expected_volume_mounts_from_values(
        deployable_details: DeployableDetails, container_name: str, with_hooks: bool
    ):
        container_details = deployable_details.deployable_details_for_container(container_name)
        if not container_details:
            return []
        volume_mounts = deepfreeze(
            container_details.get_helm_values(values, PropertyType.VolumeMounts, default_value=None)
        )
        if not volume_mounts:
            return []
        expected_volume_mounts = []
        for v in volume_mounts:
            new_volume_mount = v
            if new_volume_mount.get("mountContext"):
                if with_hooks is None:
                    raise RuntimeError(
                        f"{container_details.name} : Encountered a volume mount with mountContext, "
                        f"but we expected none : {v}"
                    )
                elif (
                    v.get("mountContext") == "hook"
                    and with_hooks
                    or v.get("mountContext") == "runtime"
                    and not with_hooks
                ):
                    new_volume_mount = new_volume_mount.delete("mountContext")
                else:
                    continue
            expected_volume_mounts.append(new_volume_mount)
        return expected_volume_mounts

    template_containers_volumes_mounts = {}
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                volumes_mounts = deepfreeze(container.get("volumeMounts", []))
                pod_container_volumes = volumes_mounts
                template_containers_volumes_mounts[f"{template_id(template)}/{container['name']}"] = (
                    pod_container_volumes
                )

    iterate_deployables_workload_parts(set_extra_volume_mounts)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert "volumeMounts" in container, (
                    f"Pod container {template_id(template)}/{container['name']} does not have volumeMounts"
                )
                volumes_mounts = deepfreeze(container["volumeMounts"])
                deployable_details = template_to_deployable_details(template)
                container_details = deployable_details.deployable_details_for_container(container["name"])
                if container_details.has_mount_context:
                    if template["metadata"].get("annotations", {}).get("helm.sh/hook-weight"):
                        assert set(volumes_mounts) - set(
                            template_containers_volumes_mounts[f"{template_id(template)}/{container['name']}"]
                        ) == set(
                            get_expected_volume_mounts_from_values(
                                deployable_details, container["name"], with_hooks=True
                            )
                        ), f"Pod container {template_id(template)}/{container['name']} volume mounts {volumes_mounts}"
                    else:
                        assert set(volumes_mounts) - set(
                            template_containers_volumes_mounts[f"{template_id(template)}/{container['name']}"]
                        ) == set(
                            get_expected_volume_mounts_from_values(
                                deployable_details, container["name"], with_hooks=False
                            )
                        ), f"Pod container {template_id(template)}/{container['name']} volume mounts {volumes_mounts}"
                else:
                    assert set(volumes_mounts) - set(
                        template_containers_volumes_mounts[f"{template_id(template)}/{container['name']}"]
                    ) == set(
                        get_expected_volume_mounts_from_values(deployable_details, container["name"], with_hooks=None)
                    ), f"Pod container {template_id(template)}/{container['name']} volume mounts {volumes_mounts}"
                    " is missing expected extra volume"
