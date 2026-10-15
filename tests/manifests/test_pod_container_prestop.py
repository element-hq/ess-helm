# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import PropertyType, values_files_to_test
from .utils import (
    PERSISTENT_WORKLOAD_KINDS,
    iterate_deployables_parts,
    iterate_pod_template,
)

# When a non-singleton workload is rolled out, its old pods are killed while new pods
# serve traffic. The Service's iptables rules must be updated before a pod is killed.
# Without a wait, clients keep sending requests to the killed pod.
# Workloads that handle graceful shutdown themselves, like HAProxy, are marked with
# has_native_graceful_shutdown in the test details and must not have the preStop sleep.
# Singleton workloads are not killed during a rolling rollout, so they do not need it either.


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_non_singleton_workloads_have_prestop_sleep_by_default(values, templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        deployable_details = pod_template_details.deployable_details()
        no_prestop_needed = deployable_details.is_singleton or deployable_details.has_native_graceful_shutdown

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            prestop = container.get("lifecycle", {}).get("preStop")
            if no_prestop_needed:
                # Some workloads have their own preStop, like Postgres with pg_ctl.
                # They just must not have a sleep-based preStop.
                assert prestop is None or "sleep" not in prestop, (
                    f"{id} has a preStop sleep although it does not need one"
                )
            else:
                expected_sleep = deployable_details.get_helm_values(values, PropertyType.PreStopSleepSeconds, 3)
                assert prestop == {"sleep": {"seconds": expected_sleep}}, (
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
            deployable_details.has_workloads and not deployable_details.is_singleton and not deployable_details.is_hook
        ),
    )

    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        deployable_details = pod_template_details.deployable_details()
        no_prestop_needed = deployable_details.is_singleton or deployable_details.has_native_graceful_shutdown

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            prestop = container.get("lifecycle", {}).get("preStop")
            if no_prestop_needed:
                # Some workloads have their own preStop, like Postgres with pg_ctl.
                # They just must not have a sleep-based preStop.
                assert prestop is None or "sleep" not in prestop, (
                    f"{id} has a preStop sleep although it does not need one"
                )
            else:
                expected_sleep = deployable_details.get_helm_values(values, PropertyType.PreStopSleepSeconds)
                assert prestop == {"sleep": {"seconds": expected_sleep}}, (
                    f"{id} should sleep {expected_sleep} seconds before stopping. "
                    "This gives the Service time to update its iptables rules before the pod is killed"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_non_singleton_workloads_can_unset_prestop_sleep(values, make_templates):
    def unset_prestop_sleep_details(deployable_details):
        # Setting the value to null removes the preStop sleep from the workload
        deployable_details.set_helm_values(values, PropertyType.PreStopSleepSeconds, None)

    iterate_deployables_parts(
        unset_prestop_sleep_details,
        lambda deployable_details: (
            deployable_details.has_workloads and not deployable_details.is_singleton and not deployable_details.is_hook
        ),
    )

    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        deployable_details = pod_template_details.deployable_details()
        no_prestop_needed = deployable_details.is_singleton or deployable_details.has_native_graceful_shutdown
        if no_prestop_needed:
            # These workloads can have their own preStop, like Postgres with pg_ctl
            continue

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            prestop = container.get("lifecycle", {}).get("preStop")
            assert prestop is None, f"{id} has a preStop although preStopSleepSeconds is unset"
