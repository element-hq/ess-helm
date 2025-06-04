# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_deployments_set_replicas(templates):
    deployments = []
    for template in templates:
        if template["kind"] in ["Deployment"]:
            deployments.append(template)

    for deployment in deployments:
        id = deployment["metadata"]["name"]
        assert "replicas" in deployment["spec"], f"{id} does not specify replicas"


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


def assert_matching_replicas(template, values):
    deployable_details = template_to_deployable_details(template)
    replicas = template["spec"]["replicas"]
    max_unavailable = template["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"]
    if deployable_details.has_replicas:
        value = deployable_details.get_helm_values(values, PropertyType.Replicas)
        assert value == replicas, (
            f"{template_id(template)} of {deployable_details.name} has replicas {replicas} where {replicas} != {value}"
        )
        assert max_unavailable == 1, (
            f"{template_id(template)} has maxUnavailable {max_unavailable} where {max_unavailable} != 1"
        )
    else:
        assert replicas == 1, (
            f"{template_id(template)} has replicas {replicas} "
            f"when replicas should not be settable present when it should be absent"
        )
        assert max_unavailable == 0, (
            f"{template_id(template)} has maxUnavailable {max_unavailable} where {max_unavailable} != 0"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_deployments_can_set_replicas(values, make_templates):
    set_replicas_details(values)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment"]:
            assert_matching_replicas(template, values)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_max_unaivalable_single_replicas(values, make_templates):
    iterate_deployables_parts(
        lambda deployable_details: deployable_details.set_helm_values(values, PropertyType.Replicas, 1),
        lambda deployable_details: deployable_details.has_replicas,
    )
    for template in await make_templates(values):
        if template["kind"] in ["Deployment"]:
            replicas = template["spec"]["replicas"]
            max_unavailable = template["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"]
            assert replicas == 1, f"{template_id(template)} has replicas {replicas} when replicas != 1"
            assert max_unavailable == 0, (
                f"{template_id(template)} has maxUnavailable {max_unavailable} where {max_unavailable} != 0"
            )
