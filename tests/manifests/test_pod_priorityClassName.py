# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    template_id,
    template_to_deployable_details,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_priorityClassName_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "priorityClassName" not in pod_spec, (
                f"{template_id(template)} has a default priorityClassName when one isn't configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_priorityClassName(values, make_templates, release_name):
    def set_priorityClassName(deployable_details: DeployableDetails):
        priorityClassName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.PriorityClassName, priorityClassName)

    iterate_deployables_workload_parts(set_priorityClassName)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "priorityClassName" in pod_spec, (
                f"{template_id(template)} doesn't have a priorityClassName when one is configured"
            )

            deployable_details = template_to_deployable_details(template)
            expected_priorityClassName = deployable_details.get_helm_values(values, PropertyType.PriorityClassName)
            assert pod_spec["priorityClassName"] == expected_priorityClassName, (
                f"{template_id(template)} has an unexpected priorityClassName"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_priorityClassName_renders(values, make_templates):
    global_priorityClassName = "global-priority"
    values["priorityClassName"] = global_priorityClassName

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert pod_spec.get("priorityClassName") == global_priorityClassName, (
                f"{template_id(template)} doesn't inherit the global priorityClassName"
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
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            deployable_details = template_to_deployable_details(template)
            expected_priorityClassName = deployable_details.get_helm_values(values, PropertyType.PriorityClassName)
            assert pod_spec.get("priorityClassName") == expected_priorityClassName, (
                f"{template_id(template)} did not let its component priorityClassName override the global one"
            )
            assert pod_spec["priorityClassName"] != global_priorityClassName, (
                f"{template_id(template)} rendered the global priorityClassName instead of its component override"
            )
