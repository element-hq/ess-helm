# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml

from . import services_values_files_to_test, values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_services_are_named(templates):
    for template in templates:
        if template["kind"] == "Service":
            port_names = []
            for port in template["spec"]["ports"]:
                assert "name" in port, f"{template_id(template)} has a port without a name: {port}"
                port_names.append(port["name"])
            assert len(port_names) == len(set(port_names)), (
                f"Port names are not unique: {template_id(template)}, {port_names}"
            )


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_not_too_many_ports_in_services(templates):
    for template in templates:
        if template["kind"] == "Service":
            assert "ports" in template["spec"], f"{template_id(template)} does not specify a ports list"

            number_of_ports = len(template["spec"]["ports"])
            assert number_of_ports > 0, f"{template_id(template)} does not include any ports"
            assert number_of_ports <= 250, f"{template_id(template)} has more than 250 ports"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_references_to_services_are_anchored_by_the_cluster_domain(values, make_templates):
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.cluster.local." in line, (
                    f"{template_id(template)} has {line=} which has a reference to a Service that isn't "
                    "anchored with the default cluster domain"
                )

    values["clusterDomain"] = "k8s.example.com."
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.k8s.example.com." in line, (
                    f"{template_id(template)} has {line=} which has a reference to a Service that isn't "
                    "anchored with the configured cluster domain"
                )
