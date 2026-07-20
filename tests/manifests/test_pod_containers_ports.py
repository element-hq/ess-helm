# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import EPHEMERAL_WORKLOAD_KINDS, PERSISTENT_WORKLOAD_KINDS, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_unique_ports_in_containers(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        ports = []
        for container in pod_template_details.pod_template["spec"]["containers"]:
            ports += [port["containerPort"] for port in container.get("ports", [])]
        assert len(ports) == len(set(ports)), f"Ports are not unique: {pod_template_details.manifest_id}, {ports}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_containers_are_named(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        port_names = []
        for container in pod_template_details.pod_template["spec"]["containers"]:
            for port in container.get("ports", []):
                assert "name" in port, f"{id} has container {container['name']} which has a port without a name: {port}"
                port_names.append(port["name"])
        assert len(port_names) == len(set(port_names)), (
            f"Port names are not unique: {pod_template_details.manifest_id}, {port_names}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ports_in_jobs(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=EPHEMERAL_WORKLOAD_KINDS):
        ports = []
        for container in pod_template_details.pod_template["spec"]["containers"]:
            ports += [port["containerPort"] for port in container.get("ports", [])]
        assert len(ports) == 0, f"Ports are present in job: {pod_template_details.manifest_id}, {ports}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_not_too_many_container_ports(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        for container in pod_template_details.pod_template["spec"]["containers"]:
            number_of_ports = len(container.get("ports", []))
            # This limit is fairly arbitrary. Unlike with Services (which have a limit of 250 ports),
            # there doesn't appear to be a hard limit of number of ports on a Pod/container. However if
            # you go wild you hit maximum document size when attempting to put the manifest into the
            # cluster. 100 is chosen as anything more quickly makes `kubectl {describe,get}` unusable.
            # Container ports are "just" metadata, albeit one which helps the scheduler if `hostPorts`
            # are involved
            assert number_of_ports < 100, (
                f"{pod_template_details.manifest_id}/{container['name']} has too many ports ({number_of_ports} >= 100)"
            )
