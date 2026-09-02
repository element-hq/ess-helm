# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    assert_covers_expected_workloads,
    find_services_matching_selector,
    find_workload_ids_matching_selector,
    iterate_deployables_parts,
    template_id,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitored_as_appropriate(values: dict, make_templates):
    def workload_ids_covered_by_service_monitor(
        service_monitor_template: dict[str, Any], templates_by_kind: dict[str, list[dict[str, Any]]]
    ):
        service_templates = templates_by_kind["Service"]
        matching_service_templates = find_services_matching_selector(
            service_templates, service_monitor_template["spec"]["selector"]["matchLabels"]
        )
        assert matching_service_templates != []

        covered_workload_ids = set[str]()
        for matching_service_template in matching_service_templates:
            new_covered_workload_ids = find_workload_ids_matching_selector(
                templates_by_kind.get("Deployment", []) + templates_by_kind.get("StatefulSet", []),
                matching_service_template["spec"]["selector"],
            )
            assert new_covered_workload_ids != set()
            assert covered_workload_ids.intersection(new_covered_workload_ids) == set()
            covered_workload_ids.update(new_covered_workload_ids)
        return covered_workload_ids

    await assert_covers_expected_workloads(
        values,
        make_templates,
        "ServiceMonitor",
        PropertyType.ServiceMonitor,
        lambda deployable_details: deployable_details.has_service_monitor,
        workload_ids_covered_by_service_monitor,
    )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_servicemonitors_created_if_no_servicemonitor_crds(values, make_templates):
    for template in await make_templates(values, has_service_monitor_crd=False):
        assert template["kind"] != "ServiceMonitor", (
            f"{template_id(template)} exists but the ServiceMonitor CRD isn't present"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitor_defaults(templates):
    for template in templates:
        if template["kind"] != "ServiceMonitor":
            continue

        component_name = template["metadata"]["labels"]["app.kubernetes.io/name"]
        if component_name == "synapse":
            assert len(template["spec"]["endpoints"][0]["relabelings"]) == 2
        elif component_name == "valkey":
            assert len(template["spec"]["endpoints"][0]["relabelings"]) == 1
        else:
            assert "relabelings" not in template["spec"]["endpoints"][0]
        assert "metricRelabelings" not in template["spec"]["endpoints"][0]


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitors_allow_adding_relabelings(values, make_templates):
    def assert_relabeling(relabeling: dict[str, Any]):
        assert relabeling["targetLabel"] == "test_label"
        assert relabeling["action"] == "replace"
        assert relabeling["replacement"] == "test_value"

    def sets_relabelings(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.ServiceMonitor,
            {
                "relabelings": [
                    {
                        "targetLabel": "test_label",
                        "action": "replace",
                        "replacement": "test_value",
                    }
                ]
            },
        )

    iterate_deployables_parts(sets_relabelings, lambda deployable_details: deployable_details.has_service_monitor)

    for template in await make_templates(values):
        if template["kind"] != "ServiceMonitor":
            continue

        component_name = template["metadata"]["labels"]["app.kubernetes.io/name"]
        if component_name == "synapse":
            assert len(template["spec"]["endpoints"][0]["relabelings"]) == 3
            assert_relabeling(template["spec"]["endpoints"][0]["relabelings"][2])
        elif component_name == "valkey":
            assert len(template["spec"]["endpoints"][0]["relabelings"]) == 2
            assert_relabeling(template["spec"]["endpoints"][0]["relabelings"][1])
        else:
            assert len(template["spec"]["endpoints"][0]["relabelings"]) == 1
            assert_relabeling(template["spec"]["endpoints"][0]["relabelings"][0])


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitors_allow_adding_metric_relabelings(values, make_templates):
    def assert_metric_relabeling(relabeling: dict[str, Any]):
        assert relabeling["targetLabel"] == "test_metric_label"
        assert relabeling["action"] == "replace"
        assert relabeling["replacement"] == "test_metric_value"

    def sets_metric_relabelings(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.ServiceMonitor,
            {
                "metricRelabelings": [
                    {
                        "targetLabel": "test_metric_label",
                        "action": "replace",
                        "replacement": "test_metric_value",
                    }
                ]
            },
        )

    iterate_deployables_parts(
        sets_metric_relabelings, lambda deployable_details: deployable_details.has_service_monitor
    )

    for template in await make_templates(values):
        if template["kind"] != "ServiceMonitor":
            continue

        assert len(template["spec"]["endpoints"][0]["metricRelabelings"]) == 1
        assert_metric_relabeling(template["spec"]["endpoints"][0]["metricRelabelings"][0])
