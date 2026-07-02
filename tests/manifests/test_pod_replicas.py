# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pyhelm3
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
        # This is here as we used to set podAntiAffinity based on the value of replicas
        # Until we allow for configurable affinity, we'll assert it here
        assert "affinity" not in template["spec"]["template"]["spec"], (
            f"{template_id(template)} has affinity where we don't allow configuration of affinity"
        )

        deployable_details = template_to_deployable_details(template)
        # Because some values files set replicas to >1
        expected_replicas = deployable_details.get_helm_values(values, PropertyType.Replicas, 1)
        assert template["spec"]["replicas"] == expected_replicas, (
            f"{template_id(template)} has incorrect replicas value"
        )

        if template["kind"] == "Deployment":
            max_unavailable = template["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"]
            if expected_replicas > 1:
                assert max_unavailable == 1, (
                    f"{template_id(template)} has {max_unavailable=} when it should be 1 with more than 1 replica"
                )
            else:
                assert max_unavailable == 0, (
                    f"{template_id(template)} has {max_unavailable=} when it should be 0 with no replicas"
                )
            max_surge = template["spec"]["strategy"]["rollingUpdate"]["maxSurge"]
            assert max_surge == 2, f"{template_id(template)} has {max_surge=} when it should be 2"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_deployments_statefulsets_respect_replicas(values, make_templates):
    set_replicas_details(values)
    for template in await make_templates(values):
        if template["kind"] not in ["Deployment", "StatefulSet"]:
            continue

        assert "replicas" in template["spec"], f"{template_id(template)} does not specify replicas"
        # This is here as we used to set podAntiAffinity based on the value of replicas
        # Until we allow for configurable affinity, we'll assert it here
        assert "affinity" not in template["spec"]["template"]["spec"], (
            f"{template_id(template)} has affinity where we don't allow configuration of affinity"
        )

        deployable_details = template_to_deployable_details(template)
        expected_replicas = deployable_details.get_helm_values(values, PropertyType.Replicas)
        assert expected_replicas == template["spec"]["replicas"], (
            f"{template_id(template)} has incorrect replicas value"
        )

        if template["kind"] == "Deployment":
            max_unavailable = template["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"]
            if template_to_deployable_details(template).is_singleton:
                assert max_unavailable == 0, (
                    f"{template_id(template)} has {max_unavailable=} when it should be 0 with singletons:"
                )
            else:
                assert max_unavailable == 1, (
                    f"{template_id(template)} has {max_unavailable=} when it should be 1 with more than 1 replica"
                )


def set_replicas_details(values):
    # We have a counter that increments for each replicas field for each deployable details
    # That way we can assert a) the correct value is going into the correct field and
    # b) that the correct part of the values file is being used
    counter = 100

    def set_replicas_details(deployable_details: DeployableDetails):
        nonlocal counter
        counter += 1
        # For singletons, we check that we can disable pod replicas
        if deployable_details.is_singleton:
            deployable_details.set_helm_values(values, PropertyType.Replicas, 0)
        else:
            deployable_details.set_helm_values(values, PropertyType.Replicas, counter)

    iterate_deployables_parts(set_replicas_details, lambda deployable_details: True)


@pytest.mark.parametrize("values_file", ["all-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_singleton_cannot_have_more_than_one_replicas(values, make_templates):
    found_deployables = []

    def set_2_replicas(deployable_details: DeployableDetails):
        nonlocal found_deployables
        deployable_details.set_helm_values(values, PropertyType.Replicas, 2)
        found_deployables.append(deployable_details)

    iterate_deployables_parts(
        set_2_replicas,
        lambda deployable_details: deployable_details.is_singleton,
    )

    async def render_and_assert_error():
        await make_templates(values)
        for deployable_details in found_deployables:
            # ruff: disable[PT017]
            replicas_values_file_path = deployable_details.get_values_file_path(PropertyType.Replicas)
            assert replicas_values_file_path
            replicas_values_file_path.assert_is_in_error_message(e, ": maximum: got 2, want 1")

    with pytest.raises(pyhelm3.errors.Error) as e:
        await render_and_assert_error()
