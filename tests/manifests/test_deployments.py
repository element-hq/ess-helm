# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_deployments_set_replicas(templates):
    for template in templates:
        if template["kind"] in ["Deployment"]:
            assert "replicas" in template["spec"], f"{template_id(template)} does not specify replicas"


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


def assert_matching_replicas(template, values, release_name):
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
        pod_spec = template["spec"]["template"]["spec"]
        assert "affinity" in pod_spec, f"{template_id(template)} is missing affinity"
        assert "podAntiAffinity" in pod_spec["affinity"], f"{template_id(template)} missing podAntiAffinity"
        assert "preferredDuringSchedulingIgnoredDuringExecution" in pod_spec["affinity"]["podAntiAffinity"], (
            f"{template_id(template)} Missing preferredDuringSchedulingIgnoredDuringExecution in podAntiAffinity"
        )
        assert len(pod_spec["affinity"]["podAntiAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"]) >= 1, (
            f"{template_id(template)} No items in preferredDuringSchedulingIgnoredDuringExecution"
        )

        item = pod_spec["affinity"]["podAntiAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"][0]
        assert "labelSelector" in item, (
            f"{template_id(template)} Missing labelSelector in preferredDuringSchedulingIgnoredDuringExecution item"
        )
        assert "matchExpressions" in item["labelSelector"], (
            f"{template_id(template)} Missing matchExpressions in labelSelector"
        )
        assert len(item["labelSelector"]["matchExpressions"]) >= 1, (
            f"{template_id(template)} No matchExpressions in labelSelector"
        )

        match_expr = item["labelSelector"]["matchExpressions"][0]
        assert "key" in match_expr, f"{template_id(template)} Missing key in matchExpression"
        assert "operator" in match_expr, f"{template_id(template)} Missing operator in matchExpression"
        assert "values" in match_expr, f"{template_id(template)} Missing values in matchExpression"

        assert match_expr["key"] == "app.kubernetes.io/instance", (
            f"{template_id(template)} Incorrect key in matchExpression"
        )
        assert match_expr["operator"] == "In", f"{template_id(template)} Incorrect operator in matchExpression"
        assert isinstance(match_expr["values"], list), (
            f"{template_id(template)} values should be a list in matchExpression"
        )
        assert len(match_expr["values"]) == 1, (
            f"{template_id(template)} values should have exactly one item in matchExpression"
        )
        assert isinstance(match_expr["values"][0], str), (
            f"{template_id(template)} values should be a string in matchExpression"
        )
        assert match_expr["values"][0] == template["metadata"]["labels"]["app.kubernetes.io/instance"]
        assert (
            match_expr["values"][0] == template["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/instance"]
        )
    else:
        assert replicas == 1, (
            f"{template_id(template)} has replicas {replicas} "
            f"when replicas should not be settable present when it should be absent"
        )
        assert max_unavailable == 0, (
            f"{template_id(template)} has maxUnavailable {max_unavailable} where {max_unavailable} != 0"
        )
        assert "affinity" not in template["spec"]["template"]["spec"], (
            f"{template_id(template)} has affinity where affinity should not be set with 1 replica"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_deployments_can_set_replicas(values, make_templates, release_name):
    set_replicas_details(values)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment"]:
            assert_matching_replicas(template, values, release_name)


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
            assert "affinity" not in template["spec"]["template"]["spec"], (
                f"{template_id(template)} has affinity where affinity should not be set with 1 replica"
            )
