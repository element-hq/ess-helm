# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from . import secret_values_files_to_test, values_files_to_test
from .utils import template_id, workload_spec_containers


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_volumes_mounts_exists(release_name, templates, other_secrets, other_configmaps):
    configmaps_names = [t["metadata"]["name"] for t in templates if t["kind"] == "ConfigMap"] + [
        s["metadata"]["name"] for s in other_configmaps
    ]
    secrets_names = [t["metadata"]["name"] for t in templates if t["kind"] == "Secret"] + [
        s["metadata"]["name"] for s in other_secrets
    ]
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
                    assert re.match(r"^((as)-\d+|(secret)-[a-f0-9]{12}|secret-generated)$", volume["name"]), (
                        f"{template_id(template)} contains a Secret mounted with an unexpected name: {volume['name']}"
                    )
                if "configMap" in volume:
                    assert volume["configMap"]["name"] in configmaps_names, (
                        f"Volume {volume['configMap']['name']} not found in ConfigMap names:"
                        f"{configmaps_names} for {template_id(template)}"
                    )
                    assert volume["name"] in [
                        "config",
                        "haproxy-config",
                        "nginx-config",
                        "plain-config",
                        "plain-syn-config",
                        "plain-mas-config",
                        "synapse-haproxy",
                        "well-known-haproxy",
                    ], f"{template_id(template)} contains a ConfigMap mounted with an unexpected name: {volume['name']}"
            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                for volume_mount in container.get("volumeMounts", []):
                    assert volume_mount["name"] in volumes_names, (
                        f"Volume Mount {volume_mount['name']} not found in volume names: {volumes_names} "
                        f"for {template_id(template)}/{container['name']}"
                    )
