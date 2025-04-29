# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterator
from typing import Any

import pytest

from . import DeployableDetails, values_files_to_test
from .utils import iterate_deployables_parts, template_id


def selector_match(labels: dict[str, str], selector: dict[str, str]) -> bool:
    return all(labels[key] == value for key, value in selector.items())


def find_services_matching_selector(templates: Iterator[Any], selector: dict[str, str]) -> list[Any]:
    services = []
    for template in templates:
        if template["kind"] == "Service" and selector_match(template["metadata"]["labels"], selector):
            services.append(template)
    return services


def find_workload_ids_matching_selector(templates: Iterator[Any], selector: dict[str, str]) -> list[str]:
    workload_ids = []
    for template in templates:
        if template["kind"] in ("Deployment", "StatefulSet", "Job") and selector_match(
            template["spec"]["template"]["metadata"]["labels"], selector
        ):
            workload_ids.append(f"{template['kind']}/{template['metadata']['name']}")

    return workload_ids


def workload_ids_for_service_monitor(service_monitor, templates) -> set[str]:
    services = find_services_matching_selector(templates, service_monitor["spec"]["selector"]["matchLabels"])
    assert len(services) > 0, f"No Services behind ServiceMonitor {service_monitor['metadata']['name']}"

    workload_ids = []
    for service in services:
        workload_ids.extend(find_workload_ids_matching_selector(templates, service["spec"]["selector"]))

    assert len(workload_ids) > 0, f"No workloads behind ServiceMonitor {service_monitor['metadata']['name']}"
    assert len(workload_ids) == len(set(workload_ids)), (
        f"ServiceMonitor {service_monitor['metadata']['name']} covers same workloads multiple times"
    )
    return set(workload_ids)


def workload_ids_monitored(templates: Iterator[Any]) -> set[str]:
    workload_ids_monitored = set[str]()
    for template in templates:
        if template["kind"] == "ServiceMonitor":
            these_monitored_workload_ids = workload_ids_for_service_monitor(template, templates)
            assert workload_ids_monitored.intersection(these_monitored_workload_ids) == set(), (
                "Multiple ServiceMonitors cover the same workload"
            )
            workload_ids_monitored.update(these_monitored_workload_ids)

    return workload_ids_monitored


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_monitored_as_appropriate(
    deployables_details, values: dict, make_templates, template_to_deployable_details
):
    # If the component and all its sub-components don't have ServiceMonitors we should assert that
    if not any([deployable_details.has_service_monitor for deployable_details in deployables_details]):
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            assert template["kind"] != "ServiceMonitor", (
                f"{deployable_details.name} unexpectedly has a ServiceMonitor: {template=}"
            )

        return

    def disable_service_monitor(values_fragment: dict[str, Any], deployable_details: DeployableDetails):
        if deployable_details.has_service_monitor:
            values_fragment.setdefault("serviceMonitors", {}).setdefault("enabled", False)
        else:
            values_fragment.setdefault("labels", {}).setdefault("servicemonitor", "none")

    iterate_deployables_parts(
        deployables_details,
        values,
        disable_service_monitor,
        lambda deployable_details: True,
        ignore_uses_parent_properties=True,
    )

    # We should now have no ServiceMonitors rendered
    workloads_to_cover = set()
    for template in await make_templates(values):
        deployable_details = template_to_deployable_details(template)
        assert template["kind"] != "ServiceMonitor", (
            f"{deployable_details.name} unexpectedly has a ServiceMonitor when all are turned off"
        )
        if (
            template["kind"] in ["Deployment", "StatefulSet", "Job"]
            and template["metadata"]["labels"].get("servicemonitor", "some") != "none"
        ):
            workloads_to_cover.add(f"{template['kind']}/{template['metadata']['name']}")

    seen_covered_workloads = set[str]()

    for deployable_details in deployables_details:
        if not deployable_details.has_service_monitor:
            continue
        # We then render each component & sub-component one by one, and extract its service monitor
        # The rendered ServiceMonitors should not cover any workloads that have already been covered
        deployable_details.get_helm_values_fragment(values)["serviceMonitors"]["enabled"] = True

        new_monitored_workload_ids = workload_ids_monitored(await make_templates(values))
        assert seen_covered_workloads.intersection(new_monitored_workload_ids) == set()
        seen_covered_workloads.update(new_monitored_workload_ids)

        deployable_details.get_helm_values_fragment(values)["serviceMonitors"]["enabled"] = False

    assert seen_covered_workloads.symmetric_difference(workloads_to_cover) == set()


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_servicemonitors_created_if_no_servicemonitor_crds(values, make_templates):
    for template in await make_templates(values, has_service_monitor_crd=False):
        assert template["kind"] != "ServiceMonitor", (
            f"{template_id(template)} exists but the ServiceMonitor CRD isn't present"
        )
