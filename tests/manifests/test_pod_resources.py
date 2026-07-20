# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_resources_are_configurable(values, make_templates):
    counter = 1

    def set_resources(deployable_details: DeployableDetails):
        nonlocal counter
        resources = {
            "requests": {
                "cpu": f"{1000 + counter}",
                "memory": f"{2000 + counter}Mi",
            },
            "limits": {
                "cpu": f"{3000 + counter}",
                "memory": f"{4000 + counter}Mi",
            },
        }
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.Resources, resources)

    iterate_deployables_workload_parts(set_resources)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        for container in pod_template_details.pod_template["spec"]["containers"]:
            assert "resources" in container, (
                f"{pod_template_details.manifest_id} has container {container['name']} without resources"
            )

            deployable_details = pod_template_details.deployable_details(container["name"])
            expected_resources = deployable_details.get_helm_values(values, PropertyType.Resources)

            assert expected_resources == container["resources"], (
                f"{pod_template_details.manifest_id} has container {container['name']} "
                "which doesn't have the expected resources"
            )
