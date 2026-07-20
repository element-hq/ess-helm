# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_priorityClassName_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "priorityClassName" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a default priorityClassName when one isn't configured"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_priorityClassName(values, make_templates, release_name):
    def set_priorityClassName(deployable_details: DeployableDetails):
        priorityClassName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.PriorityClassName, priorityClassName)

    iterate_deployables_workload_parts(set_priorityClassName)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "priorityClassName" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a priorityClassName when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_priorityClassName = deployable_details.get_helm_values(values, PropertyType.PriorityClassName)
        assert pod_spec["priorityClassName"] == expected_priorityClassName, (
            f"{pod_template_details.manifest_id} has an unexpected priorityClassName"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_priorityClassName_renders(values, make_templates):
    global_priorityClassName = "global-priority"
    values["priorityClassName"] = global_priorityClassName

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec.get("priorityClassName") == global_priorityClassName, (
            f"{pod_template_details.manifest_id} doesn't inherit the global priorityClassName"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_priorityClassName_overrides_global(values, make_templates):
    global_priorityClassName = "global-priority"
    values["priorityClassName"] = global_priorityClassName

    def set_priorityClassName(deployable_details: DeployableDetails):
        component_priorityClassName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.PriorityClassName, component_priorityClassName)

    iterate_deployables_workload_parts(set_priorityClassName)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        deployable_details = pod_template_details.deployable_details()
        expected_priorityClassName = deployable_details.get_helm_values(values, PropertyType.PriorityClassName)
        assert pod_spec.get("priorityClassName") == expected_priorityClassName, (
            f"{pod_template_details.manifest_id} did not let its component priorityClassName override the global one"
        )
        assert pod_spec["priorityClassName"] != global_priorityClassName, (
            f"{pod_template_details.manifest_id} rendered the global priorityClassName "
            "instead of its component override"
        )
