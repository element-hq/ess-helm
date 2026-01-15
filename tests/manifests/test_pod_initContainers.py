# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    template_id,
    template_to_deployable_details,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_extraInitContainers(values, make_templates, release_name):
    template_id_to_init_containers = {}
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            template_id_to_init_containers[template_id(template)] = deepfreeze(pod_spec.get("initContainers", []))

    def set_initContainers(deployable_details: DeployableDetails):
        init_container = [
            {"name": f"{deployable_details.name}-extra", "image": "oci.element.io/extra-image:v1.2.3"},
            {
                "name": f"aaa-{deployable_details.name}-extra",
                "image": "oci.element.io/another-extra-image:v1.2.3",
                "env": [{"name": "A", "value": "B"}, {"name": "FOO", "value": "BAR"}],
            },
        ]
        deployable_details.set_helm_values(values, PropertyType.InitContainers, deepfreeze(init_container))

    iterate_deployables_workload_parts(set_initContainers)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "initContainers" in pod_spec, (
                f"{template_id(template)} doesn't have at least one initContainers when a custom one is configured"
            )
            init_containers = pod_spec["initContainers"]

            deployable_details = template_to_deployable_details(template)
            extra_init_containers = deployable_details.get_helm_values(values, PropertyType.InitContainers)
            # All the existing initContainers come first
            assert (template_id_to_init_containers[template_id(template)] + extra_init_containers) == init_containers
