# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pyhelm3
import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import PERSISTENT_WORKLOAD_KINDS, iterate_deployables_parts, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_deployments_statefulsets_have_replicas_by_default(values, templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        manifest_spec = pod_template_details.manifest["spec"]
        assert "replicas" in manifest_spec, f"{pod_template_details.manifest_id} does not specify replicas"
        # This is here as we used to set podAntiAffinity based on the value of replicas
        # Until we allow for configurable affinity, we'll assert it here
        assert "affinity" not in pod_template_details.pod_template["spec"], (
            f"{pod_template_details.manifest_id} has affinity where we don't allow configuration of affinity"
        )

        deployable_details = pod_template_details.deployable_details()
        # Because some values files set replicas to >1
        expected_replicas = deployable_details.get_helm_values(values, PropertyType.Replicas, 1)
        assert manifest_spec["replicas"] == expected_replicas, (
            f"{pod_template_details.manifest_id} has incorrect replicas value"
        )

        if pod_template_details.manifest["kind"] == "Deployment":
            max_unavailable = manifest_spec["strategy"]["rollingUpdate"]["maxUnavailable"]
            if expected_replicas > 1:
                assert max_unavailable == 1, (
                    f"{pod_template_details.manifest_id} has {max_unavailable=} when it should be 1 "
                    "with more than 1 replica"
                )
            else:
                assert max_unavailable == 0, (
                    f"{pod_template_details.manifest_id} has {max_unavailable=} when it should be 0 with no replicas"
                )
            max_surge = manifest_spec["strategy"]["rollingUpdate"]["maxSurge"]
            assert max_surge == 2, f"{pod_template_details.manifest_id} has {max_surge=} when it should be 2"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_deployments_statefulsets_respect_replicas(values, make_templates):
    set_replicas_details(values)
    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        manifest_spec = pod_template_details.manifest["spec"]
        assert "replicas" in manifest_spec, f"{pod_template_details.manifest_id} does not specify replicas"
        # This is here as we used to set podAntiAffinity based on the value of replicas
        # Until we allow for configurable affinity, we'll assert it here
        assert "affinity" not in manifest_spec["template"]["spec"], (
            f"{pod_template_details.manifest_id} has affinity where we don't allow configuration of affinity"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_replicas = deployable_details.get_helm_values(values, PropertyType.Replicas)
        assert expected_replicas == manifest_spec["replicas"], (
            f"{pod_template_details.manifest_id} has incorrect replicas value"
        )

        if pod_template_details.manifest["kind"] == "Deployment":
            max_unavailable = manifest_spec["strategy"]["rollingUpdate"]["maxUnavailable"]
            if deployable_details.is_singleton:
                assert max_unavailable == 0, (
                    f"{pod_template_details.manifest_id} has {max_unavailable=} when it should be 0 with singletons:"
                )
            else:
                assert max_unavailable == 1, (
                    f"{pod_template_details.manifest_id} has {max_unavailable=} when it should be 1 "
                    "with more than 1 replica"
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
