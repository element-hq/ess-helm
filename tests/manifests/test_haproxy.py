# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from . import values_files_to_test
from .utils import template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_haproxy_server_templates_reference_valid_services(templates):
    services_by_name = {}
    seen_haproxy = False
    haproxy_configmap = None
    for template in templates:
        if template["kind"] == "Service":
            services_by_name[template["metadata"]["name"]] = template
        if template_to_deployable_details(template).name != "haproxy":
            continue
        seen_haproxy = True

        if template["kind"] == "ConfigMap":
            haproxy_configmap = template

    if not seen_haproxy:
        return

    assert haproxy_configmap, "No HAProxy ConfigMap found"
    assert "haproxy.cfg" in haproxy_configmap["data"], f"{template_id(haproxy_configmap)} didn't contain haproxy.cfg"

    for line in haproxy_configmap["data"]["haproxy.cfg"].splitlines():
        if "server-template" not in line:
            continue

        server_template = re.search(
            r"server-template [a-z-]+ \d+ _(?P<port>.*?)\._tcp\.(?P<service>.*?)\.(?P<namespace>.*?)"
            r"\.svc\.cluster\.local\. ",
            line,
        )
        assert server_template, (
            f"{template_id(haproxy_configmap)} had server-template line ({line}) "
            "that did not match the expected pattern"
        )

        service_name = server_template.group("service")
        assert service_name in services_by_name, f"{service_name} is not a Service that exists"

        for port in services_by_name[service_name]["spec"].get("ports", []):
            desired_port = server_template.group("port")
            if port["name"] == desired_port:
                break
        else:
            raise AssertionError(f"{service_name} did not have a port named {desired_port} referenced in {line}")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_haproxy_config_ends_in_2_newlines(templates):
    seen_haproxy = False
    haproxy_configmap = None
    for template in templates:
        if template_to_deployable_details(template).name != "haproxy":
            continue
        seen_haproxy = True

        if template["kind"] == "ConfigMap":
            haproxy_configmap = template

    if not seen_haproxy:
        return

    assert haproxy_configmap, "No HAProxy ConfigMap found"
    assert "haproxy.cfg" in haproxy_configmap["data"], f"{template_id(haproxy_configmap)} didn't contain haproxy.cfg"
    assert haproxy_configmap["data"]["haproxy.cfg"].endswith("\n\n"), (
        f"{template_id(haproxy_configmap)}/haproxy.cfg should end with at least 2 \\n"
    )
