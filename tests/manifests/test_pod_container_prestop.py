# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import PERSISTENT_WORKLOAD_KINDS, iterate_pod_template

# When a non-singleton workload is rolled out, its old pods are killed while new pods
# serve traffic. The Service's iptables rules must be updated before a pod is killed.
# Without a wait, clients keep sending requests to the killed pod.
# Workloads that handle graceful shutdown themselves, like HAProxy, are marked with the
# "handles-graceful-shutdown-natively" pod annotation and must not have the preStop sleep.


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_non_singleton_workloads_have_prestop_sleep(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        pod_annotations = pod_template_details.pod_template["metadata"].get("annotations", {})
        if pod_annotations.get("handles-graceful-shutdown-natively") == "yes":
            continue

        # Singleton workloads are not killed during a rolling rollout, so they
        # do not need to wait before stopping.
        if pod_template_details.deployable_details().is_singleton:
            continue

        for container in pod_template_details.pod_template["spec"]["containers"]:
            id = f"{pod_template_details.manifest_id}/{container['name']}"
            prestop_sleep = container.get("lifecycle", {}).get("preStop", {}).get("sleep", {}).get("seconds")
            assert prestop_sleep == 3, (
                f"{id} should sleep 3 seconds before stopping. "
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
