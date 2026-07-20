# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_extraInitContainers(values, make_templates):
    template_id_to_init_containers = {}
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        template_id_to_init_containers[pod_template_details.manifest_id] = deepfreeze(
            pod_spec.get("initContainers", [])
        )

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
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "initContainers" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have at least one initContainers "
            "when a custom one is configured"
        )
        init_containers = pod_spec["initContainers"]

        deployable_details = pod_template_details.deployable_details()
        extra_init_containers = deployable_details.get_helm_values(values, PropertyType.InitContainers)
        # All the existing initContainers come first
        assert (
            template_id_to_init_containers[pod_template_details.manifest_id] + extra_init_containers
        ) == init_containers
