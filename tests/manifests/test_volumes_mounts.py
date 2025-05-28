# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from . import secret_values_files_to_test, values_files_to_test
from .utils import template_id


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
                assert len(volume["name"]) <= 63, f"Volume name {volume['name']} is too long: {volume['name']}"
                volumes_names.append(volume["name"])
                if "secret" in volume:
                    assert volume["secret"]["secretName"] in secrets_names
                    assert re.match(r"^((as|secret)-\d+|secret-generated)$", volume["name"]), (
                        f"{template_id(template)} contains a Secret mounted with a non-static name: {volume['name']}"
                    )
                if "configMap" in volume:
                    assert volume["configMap"]["name"] in configmaps_names
                    assert volume["name"] in [
                        "config",
                        "haproxy-config",
                        "nginx-config",
                        "plain-config",
                        "synapse-haproxy",
                        "well-known-haproxy",
                    ], f"{template_id(template)} contains a ConfigMap mounted with an unexpected name: {volume['name']}"
            for container in template["spec"]["template"]["spec"].get("containers", []) + template["spec"]["template"][
                "spec"
            ].get(
                "initContainers",
                [],
            ):
                for volume_mount in container.get("volumeMounts", []):
                    assert volume_mount["name"] in volumes_names
