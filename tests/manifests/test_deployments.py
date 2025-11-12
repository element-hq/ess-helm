# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import PropertyType, values_files_to_test
from .test_pod_replicas import set_replicas_details
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


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
        pod_spec = template["spec"]["template"]["spec"]
        assert "affinity" in pod_spec, f"{template_id(template)} is missing affinity"
        assert "podAntiAffinity" in pod_spec["affinity"], f"{template_id(template)} missing podAntiAffinity"
        assert "preferredDuringSchedulingIgnoredDuringExecution" in pod_spec["affinity"]["podAntiAffinity"], (
            f"{template_id(template)} Missing preferredDuringSchedulingIgnoredDuringExecution in podAntiAffinity"
        )
        assert len(pod_spec["affinity"]["podAntiAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"]) >= 1, (
            f"{template_id(template)} No items in preferredDuringSchedulingIgnoredDuringExecution"
        )

        preferred_item = pod_spec["affinity"]["podAntiAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"][0]
        assert "weight" in preferred_item, (
            f"{template_id(template)} Missing weight in preferredDuringSchedulingIgnoredDuringExecution item"
        )
        assert "podAffinityTerm" in preferred_item, (
            f"{template_id(template)} Missing podAffinityTerm in preferredDuringSchedulingIgnoredDuringExecution item"
        )

        pod_affinity_term = preferred_item["podAffinityTerm"]
        assert "labelSelector" in pod_affinity_term, (
            f"{template_id(template)} Missing labelSelector in preferredDuringSchedulingIgnoredDuringExecution item"
        )
        assert "matchExpressions" in pod_affinity_term["labelSelector"], (
            f"{template_id(template)} Missing matchExpressions in labelSelector"
        )
        assert len(pod_affinity_term["labelSelector"]["matchExpressions"]) >= 1, (
            f"{template_id(template)} No matchExpressions in labelSelector"
        )

        match_expr = pod_affinity_term["labelSelector"]["matchExpressions"][0]
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
async def test_all_deployments_can_set_replicas(values, make_templates):
    # This overlaps an awful lot with test_pod_replicas.test_deployments_statefulsets_respect_replicas
    # However we don't do podAntiAffinity yet for StatefulSets (why not?) so leaving this here
    set_replicas_details(values)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment"]:
            assert_matching_replicas(template, values)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_max_unavailable_single_replicas(values, make_templates):
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
