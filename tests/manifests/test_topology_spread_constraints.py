# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, workloads_values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", workloads_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sets_no_topology_spread_constraint_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            assert "topologySpreadConstraintss" not in template["spec"]["template"]["spec"], (
                f"Pod securityContext unexpectedly present for {template_id(template)}"
            )


@pytest.mark.parametrize("values_file", workloads_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_topology_spread_constraint_has_default(values, make_templates):
    def set_topology_spread_constraints(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.TopologySpreadConstraints,
            [
                {
                    "maxSkew": 1,
                    "topologyKey": "kubernetes.io/hostname",
                    "whenUnsatisfiable": "DoNotSchedule",
                }
            ],
        )

    iterate_deployables_parts(
        set_topology_spread_constraints,
        lambda deployable_details: deployable_details.has_topology_spread_constraints,
    )

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            if template_to_deployable_details(template).has_topology_spread_constraints:
                assert "topologySpreadConstraints" in template["spec"]["template"]["spec"], (
                    f"Pod topologySpreadConstraints unexpectedly absent for {template_id(template)}"
                )

                pod_topologySpreadConstraints = template["spec"]["template"]["spec"]["topologySpreadConstraints"]
                assert pod_topologySpreadConstraints[0]["maxSkew"] == 1
                assert pod_topologySpreadConstraints[0]["topologyKey"] == "kubernetes.io/hostname"
                assert pod_topologySpreadConstraints[0]["whenUnsatisfiable"] == "DoNotSchedule"
                assert pod_topologySpreadConstraints[0]["labelSelector"]["matchLabels"] == {
                    "app.kubernetes.io/instance": template["metadata"]["labels"]["app.kubernetes.io/instance"]
                }
                if template["kind"] == "Deployment":
                    assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == ["pod-template-hash"]
                else:
                    assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == []
            else:
                assert "topologySpreadConstraints" not in template["spec"]["template"]["spec"], (
                    f"Pod topologySpreadConstraints unexpectedly present for {template_id(template)}"
                )


@pytest.mark.parametrize("values_file", workloads_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_can_nuke_topology_spread_constraint_defaults(values, make_templates):
    def set_topology_spread_constraints(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.TopologySpreadConstraints,
            [
                {
                    "maxSkew": 1,
                    "topologyKey": "kubernetes.io/hostname",
                    "whenUnsatisfiable": "DoNotSchedule",
                    "labelSelector": {
                        "matchLabels": {
                            "app.kubernetes.io/testlabel": "testvalue",
                            "app.kubernetes.io/instance": None,
                        }
                    },
                    "matchLabelKeys": ["app.kubernetes.io/testlabel"],
                }
            ],
        )

    iterate_deployables_parts(
        set_topology_spread_constraints,
        lambda deployable_details: deployable_details.has_topology_spread_constraints,
    )

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            if template_to_deployable_details(template).has_topology_spread_constraints:
                assert "topologySpreadConstraints" in template["spec"]["template"]["spec"], (
                    f"Pod topologySpreadConstraints unexpectedly absent for {template_id(template)}"
                )

                pod_topologySpreadConstraints = template["spec"]["template"]["spec"]["topologySpreadConstraints"]
                assert pod_topologySpreadConstraints[0]["maxSkew"] == 1
                assert pod_topologySpreadConstraints[0]["topologyKey"] == "kubernetes.io/hostname"
                assert pod_topologySpreadConstraints[0]["whenUnsatisfiable"] == "DoNotSchedule"
                assert pod_topologySpreadConstraints[0]["labelSelector"]["matchLabels"] == {
                    "app.kubernetes.io/testlabel": "testvalue"
                }
                assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == ["app.kubernetes.io/testlabel"]
            else:
                assert "topologySpreadConstraints" not in template["spec"]["template"]["spec"], (
                    f"Pod topologySpreadConstraints unexpectedly present for {template_id(template)}"
                )
