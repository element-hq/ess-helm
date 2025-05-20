# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import secret_values_files_to_test, values_files_to_test


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_volumes_mounts_exists(templates, other_secrets):
    configmaps_names = [t["metadata"]["name"] for t in templates if t["kind"] == "ConfigMap"]
    secrets_names = [t["metadata"]["name"] for t in templates if t["kind"] == "Secret"] + [
        s["metadata"]["name"] for s in other_secrets
    ]
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            volumes_names = []
            for volume in template["spec"]["template"]["spec"].get("volumes", []):
                volumes_names.append(volume["name"])
                if "secret" in volume:
                    assert volume["secret"]["secretName"] in secrets_names
                if "configMap" in volume:
                    assert volume["configMap"]["name"] in configmaps_names
            for container in template["spec"]["template"]["spec"].get("containers", []) + template["spec"]["template"][
                "spec"
            ].get(
                "initContainers",
                [],
            ):
                for volume_mount in container.get("volumeMounts", []):
                    assert volume_mount["name"] in volumes_names
