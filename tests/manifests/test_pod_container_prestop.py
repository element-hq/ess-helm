# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import PropertyType, values_files_to_test
from .utils import (
    PERSISTENT_WORKLOAD_KINDS,
    PodTemplateDetails,
    iterate_deployables_parts,
    iterate_pod_template,
)

# When a non-singleton workload is rolled out, its old pods are killed while new pods
# serve traffic. The Service's iptables rules must be updated before a pod is killed.
# Without a wait, clients keep sending requests to the killed pod.
# Workloads that handle graceful shutdown themselves, like HAProxy, are marked with the
# "handles-graceful-shutdown-natively" pod annotation and must not have the preStop sleep.


def skip_workloads_that_do_not_need_prestop_sleep(pod_template_details: PodTemplateDetails) -> bool:
    pod_annotations = pod_template_details.pod_template["metadata"].get("annotations", {})
    if pod_annotations.get("handles-graceful-shutdown-natively") == "yes":
        return True

    # Singleton workloads are not killed during a rolling rollout, so they
    # do not need to wait before stopping.
    return pod_template_details.deployable_details().is_singleton


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_non_singleton_workloads_have_prestop_sleep_by_default(values, templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        if skip_workloads_that_do_not_need_prestop_sleep(pod_template_details):
            continue

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            deployable_details = pod_template_details.deployable_details()
            expected_sleep = deployable_details.get_helm_values(values, PropertyType.PreStopSleepSeconds, 3)
            prestop_sleep = container.get("lifecycle", {}).get("preStop", {}).get("sleep", {}).get("seconds")
            assert prestop_sleep == expected_sleep, (
                f"{id} should sleep {expected_sleep} seconds before stopping. "
                "This gives the Service time to update its iptables rules before the pod is killed"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_non_singleton_workloads_respect_prestop_sleep(values, make_templates):
    # We have a counter that increments for each preStopSleepSeconds field for each deployable details
    # That way we can assert a) the correct value is going into the correct field and
    # b) that the correct part of the values file is being used
    counter = 100

    def set_prestop_sleep_details(deployable_details):
        nonlocal counter
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.PreStopSleepSeconds, counter)

    iterate_deployables_parts(
        set_prestop_sleep_details,
        lambda deployable_details: (
            deployable_details.has_workloads
            and not deployable_details.is_singleton
            and not deployable_details.is_hook
            and deployable_details.get_values_file_path(PropertyType.PreStopSleepSeconds).write_path is not None
        ),
    )

    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        if skip_workloads_that_do_not_need_prestop_sleep(pod_template_details):
            continue

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            deployable_details = pod_template_details.deployable_details()
            expected_sleep = deployable_details.get_helm_values(values, PropertyType.PreStopSleepSeconds)
            prestop_sleep = container.get("lifecycle", {}).get("preStop", {}).get("sleep", {}).get("seconds")
            assert prestop_sleep == expected_sleep, (
                f"{id} should sleep {expected_sleep} seconds before stopping. "
                "This gives the Service time to update its iptables rules before the pod is killed"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_workloads_handling_graceful_shutdown_natively_have_no_prestop_sleep(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        pod_annotations = pod_template_details.pod_template["metadata"].get("annotations", {})
        if pod_annotations.get("handles-graceful-shutdown-natively") != "yes":
            continue

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            prestop = container.get("lifecycle", {}).get("preStop", {})
            assert "sleep" not in prestop, (
                f"{id} sleeps before stopping although it handles graceful shutdown natively. "
                "Remove the sleep or remove the handles-graceful-shutdown-natively annotation"
            )
