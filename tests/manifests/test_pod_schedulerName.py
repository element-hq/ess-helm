# Copyright 2026 Element Creations Ltd
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
async def test_pod_has_no_schedulerName_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "schedulerName" not in pod_spec, (
                f"{template_id(template)} has a default schedulerName when one isn't configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_schedulerName(values, make_templates, release_name):
    def set_schedulerName(deployable_details: DeployableDetails):
        schedulerName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.SchedulerName, schedulerName)

    iterate_deployables_workload_parts(set_schedulerName)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "schedulerName" in pod_spec, (
                f"{template_id(template)} doesn't have a schedulerName when one is configured"
            )

            deployable_details = template_to_deployable_details(template)
            expected_schedulerName = deployable_details.get_helm_values(values, PropertyType.SchedulerName)
            assert pod_spec["schedulerName"] == expected_schedulerName, (
                f"{template_id(template)} has an unexpected schedulerName"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_schedulerName_renders(values, make_templates):
    global_schedulerName = "global-scheduler"
    values["schedulerName"] = global_schedulerName

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert pod_spec.get("schedulerName") == global_schedulerName, (
                f"{template_id(template)} doesn't inherit the global schedulerName"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_schedulerName_overrides_global(values, make_templates):
    global_schedulerName = "global-scheduler"
    values["schedulerName"] = global_schedulerName

    def set_schedulerName(deployable_details: DeployableDetails):
        component_schedulerName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.SchedulerName, component_schedulerName)

    iterate_deployables_workload_parts(set_schedulerName)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            deployable_details = template_to_deployable_details(template)
            expected_schedulerName = deployable_details.get_helm_values(values, PropertyType.SchedulerName)
            assert pod_spec.get("schedulerName") == expected_schedulerName, (
                f"{template_id(template)} did not let its component schedulerName override the global one"
            )
            assert pod_spec["schedulerName"] != global_schedulerName, (
                f"{template_id(template)} rendered the global schedulerName instead of its component override"
            )
