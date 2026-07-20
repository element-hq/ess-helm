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
async def test_pod_has_no_runtimeClassName_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "runtimeClassName" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a default runtimeClassName when one isn't configured"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_runtimeClassName(values, make_templates, release_name):
    def set_runtimeClassName(deployable_details: DeployableDetails):
        runtimeClassName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.RuntimeClassName, runtimeClassName)

    iterate_deployables_workload_parts(set_runtimeClassName)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "runtimeClassName" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a runtimeClassName when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_runtimeClassName = deployable_details.get_helm_values(values, PropertyType.RuntimeClassName)
        assert pod_spec["runtimeClassName"] == expected_runtimeClassName, (
            f"{pod_template_details.manifest_id} has an unexpected runtimeClassName"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_runtimeClassName_renders(values, make_templates):
    global_runtimeClassName = "global-runtime"
    values["runtimeClassName"] = global_runtimeClassName

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec.get("runtimeClassName") == global_runtimeClassName, (
            f"{pod_template_details.manifest_id} doesn't inherit the global runtimeClassName"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_runtimeClassName_overrides_global(values, make_templates):
    global_runtimeClassName = "global-runtime"
    values["runtimeClassName"] = global_runtimeClassName

    def set_runtimeClassName(deployable_details: DeployableDetails):
        component_runtimeClassName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.RuntimeClassName, component_runtimeClassName)

    iterate_deployables_workload_parts(set_runtimeClassName)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        deployable_details = pod_template_details.deployable_details()
        expected_runtimeClassName = deployable_details.get_helm_values(values, PropertyType.RuntimeClassName)
        assert pod_spec.get("runtimeClassName") == expected_runtimeClassName, (
            f"{pod_template_details.manifest_id} did not let its component runtimeClassName override the global one"
        )
        assert pod_spec["runtimeClassName"] != global_runtimeClassName, (
            f"{pod_template_details.manifest_id} rendered the global runtimeClassName instead of its component override"
        )
