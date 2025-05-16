# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any

import pytest

from . import PropertyType, values_files_to_test
from .utils import (
    assert_covers_expected_workloads,
    find_services_matching_selector,
    find_workload_ids_matching_selector,
    template_id,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitored_as_appropriate(
    deployables_details, values: dict, make_templates, template_to_deployable_details
):
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
        deployables_details,
        values,
        make_templates,
        template_to_deployable_details,
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
