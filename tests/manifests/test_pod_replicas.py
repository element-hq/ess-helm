# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_deployments_statefulsets_have_replicas_by_default(values, templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "StatefulSet"]:
            continue

        assert "replicas" in template["spec"], f"{template_id(template)} does not specify replicas"

        deployable_details = template_to_deployable_details(template)
        value = deployable_details.get_helm_values(values, PropertyType.Replicas, 1)
        assert template["spec"]["replicas"] == value, f"{template_id(template)} has incorrect replicas value"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_deployments_statefulsets_respect_replicas(values, make_templates):
    set_replicas_details(values)
    for template in await make_templates(values):
        if template["kind"] not in ["Deployment", "StatefulSet"]:
            continue

        deployable_details = template_to_deployable_details(template)
        if deployable_details.has_replicas:
            value = deployable_details.get_helm_values(values, PropertyType.Replicas)
            assert value == template["spec"]["replicas"], f"{template_id(template)} has incorrect replicas value"
        else:
            assert template["spec"]["replicas"] == 1, f"{template_id(template)} has incorrect replicas value"


def set_replicas_details(values):
    # We have a counter that increments for each replicas field for each deployable details
    # That way we can assert a) the correct value is going into the correct field and
    # b) that the correct part of the values file is being used
    counter = 100

    def set_replicas_details(deployable_details: DeployableDetails):
        nonlocal counter
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.Replicas, counter)

    iterate_deployables_parts(set_replicas_details, lambda deployable_details: deployable_details.has_replicas)
