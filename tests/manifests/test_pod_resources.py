# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_resources_are_configurable(
    deployables_details, values, make_templates, template_to_deployable_details
):
    deployable_details_to_resources = {}
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
        deployable_details_to_resources[deployable_details] = resources
        deployable_details.set_helm_values(values, PropertyType.Resources, resources)

    iterate_deployables_workload_parts(deployables_details, set_resources)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            for container in template["spec"]["template"]["spec"]["containers"]:
                assert "resources" in container, (
                    f"{template_id(template)} has container {container['name']} without resources"
                )

                deployable_details = template_to_deployable_details(template, container["name"])

                # The check config job gets its resources from Synapse and doesn't have its own values
                # We don't have a good way of "redirecting" to Synapse's expected resources so just skip
                # test_synapse_resources_shared_by_default tests that the check config job uses synapse.resources
                if deployable_details.name == "synapse-check-config-hook":
                    continue

                expected_resources = deployable_details_to_resources[deployable_details]
                assert expected_resources == container["resources"], (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected resources"
                )
