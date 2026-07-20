# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from frozendict import frozendict

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sets_default_topologySpreadConstraints(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "topologySpreadConstraints" in pod_spec, (
            f"Pod topologySpreadConstraints unexpectedly absent for {pod_template_details.manifest_id}"
        )

        pod_topologySpreadConstraints = pod_spec["topologySpreadConstraints"]
        assert pod_topologySpreadConstraints[0]["maxSkew"] == 1
        assert pod_topologySpreadConstraints[0]["topologyKey"] == "kubernetes.io/hostname"
        assert pod_topologySpreadConstraints[0]["whenUnsatisfiable"] == "ScheduleAnyway"
        assert pod_topologySpreadConstraints[0]["labelSelector"]["matchLabels"] == {
            "app.kubernetes.io/instance": pod_template_details.manifest["metadata"]["labels"][
                "app.kubernetes.io/instance"
            ]
        }
        if pod_template_details.manifest["kind"] == "Deployment":
            assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == ("pod-template-hash",)
        else:
            assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == tuple()


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_can_unset_global_topologySpreadConstraints(values, make_templates):
    values["topologySpreadConstraints"] = []
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        assert "topologySpreadConstraints" not in pod_template_details.pod_template["spec"], (
            f"Pod securityContext unexpectedly present for {pod_template_details.manifest_id}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_topology_spread_constraint_enriches_with_default_settings(values, make_templates):
    def set_topology_spread_constraints(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.TopologySpreadConstraints,
            [
                # Picking different values from those in the default global
                # topologySpreadConstraints to show it overrides
                {
                    "maxSkew": 2,
                    "topologyKey": "kubernetes.io/zone",
                }
            ],
        )

    iterate_deployables_workload_parts(set_topology_spread_constraints)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "topologySpreadConstraints" in pod_spec, (
            f"Pod topologySpreadConstraints unexpectedly absent for {pod_template_details.manifest_id}"
        )

        pod_topologySpreadConstraints = pod_spec["topologySpreadConstraints"]
        assert pod_topologySpreadConstraints[0]["maxSkew"] == 2
        assert pod_topologySpreadConstraints[0]["topologyKey"] == "kubernetes.io/zone"
        assert pod_topologySpreadConstraints[0]["whenUnsatisfiable"] == "DoNotSchedule"
        assert pod_topologySpreadConstraints[0]["labelSelector"]["matchLabels"] == {
            "app.kubernetes.io/instance": pod_template_details.manifest["metadata"]["labels"][
                "app.kubernetes.io/instance"
            ]
        }
        if pod_template_details.manifest["kind"] == "Deployment":
            assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == ("pod-template-hash",)
        else:
            assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == tuple()


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_can_nuke_topology_spread_constraint_default_settings(values, make_templates):
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

    iterate_deployables_workload_parts(set_topology_spread_constraints)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "topologySpreadConstraints" in pod_spec, (
            f"Pod topologySpreadConstraints unexpectedly absent for {pod_template_details.manifest_id}"
        )

        pod_topologySpreadConstraints = pod_spec["topologySpreadConstraints"]
        assert pod_topologySpreadConstraints[0]["maxSkew"] == 1
        assert pod_topologySpreadConstraints[0]["topologyKey"] == "kubernetes.io/hostname"
        assert pod_topologySpreadConstraints[0]["whenUnsatisfiable"] == "DoNotSchedule"
        assert pod_topologySpreadConstraints[0]["labelSelector"]["matchLabels"] == frozendict(
            {"app.kubernetes.io/testlabel": "testvalue"}
        )
        assert pod_topologySpreadConstraints[0]["matchLabelKeys"] == ("app.kubernetes.io/testlabel",)
