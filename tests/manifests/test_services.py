# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import services_values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_services_are_named(templates):
    for template in templates:
        if template["kind"] == "Service":
            id = template_id(template)
            assert "ports" in template["spec"], f"{id} does not specify a ports list"
            assert len(template["spec"]["ports"]) > 0, f"{id} does not include any ports"

            port_names = []
            for port in template["spec"]["ports"]:
                assert "name" in port, f"{id} has a port without a name: {port}"
                port_names.append(port["name"])
            assert len(port_names) == len(set(port_names)), f"Port names are not unique: {id}, {port_names}"
