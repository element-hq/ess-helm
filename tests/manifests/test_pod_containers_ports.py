# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_unique_ports_in_containers(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            ports = []
            for container in template["spec"]["template"]["spec"]["containers"]:
                ports += [port["containerPort"] for port in container.get("ports", [])]
            assert len(ports) == len(set(ports)), f"Ports are not unique: {template_id(template)}, {ports}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_containers_are_named(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            port_names = []
            for container in template["spec"]["template"]["spec"]["containers"]:
                for port in container.get("ports", []):
                    assert "name" in port, (
                        f"{id} has container {container['name']} which has a port without a name: {port}"
                    )
                    port_names.append(port["name"])
            assert len(port_names) == len(set(port_names)), (
                f"Port names are not unique: {template_id(template)}, {port_names}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ports_in_jobs(templates):
    for template in templates:
        if template["kind"] in ["Job"]:
            ports = []
            for container in template["spec"]["template"]["spec"]["containers"]:
                ports += [port["containerPort"] for port in container.get("ports", [])]
            assert len(ports) == 0, f"Ports are present in job: {template_id(template)}, {ports}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_not_too_many_container_ports(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            for container in template["spec"]["template"]["spec"]["containers"]:
                number_of_ports = len(container.get("ports", []))
                # This limit is fairly arbitrary. Unlike with Services (which have a limit of 250 ports),
                # there doesn't appear to be a hard limit of number of ports on a Pod/container. However if
                # you go wild you hit maximum document size when attempting to put the manifest into the
                # cluster. 100 is chosen as anything more quickly makes `kubectl {describe,get}` unusable.
                # Container ports are "just" metadata, albeit one which helps the scheduler if `hostPorts`
                # are involved
                assert number_of_ports < 100, (
                    f"{template_id(template)}/{container['name']} has too many ports ({number_of_ports} >= 100)"
                )
