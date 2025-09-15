# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml

from .utils import template_id


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_log_level_overrides(values, make_templates):
    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "matrix-rtc-sfu" in template["metadata"]["name"]
            and "config-overrides.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["config-overrides.yaml"])
            tcp_port = log_yaml["rtc"]["tcp_port"]
            assert tcp_port == 30881
            break
    else:
        raise RuntimeError("Could not find config-overrides.yaml")


async def get_sfu_udp_port_range_services(start_port, end_point, values, make_templates):
    values["matrixRTC"]["sfu"]["exposedServices"]["rtcUdp"]["portRange"]["startPort"] = start_port
    values["matrixRTC"]["sfu"]["exposedServices"]["rtcUdp"]["portRange"]["endPort"] = end_point

    services = []
    for template in await make_templates(values):
        if template["kind"] == "Service" and "matrix-rtc-sfu-udp-range" in template["metadata"]["name"]:
            services.append(template)
    return services


def assert_sharded_udp_range_ports(start_port, end_port, service):
    id = template_id(service)
    service_ports = service["spec"]["ports"]
    assert len(service_ports) == (end_port - start_port + 1), f"{id} doesn't have the correct number of ports in it"

    assert service_ports[0]["port"] == start_port, f"{id} doesn't start with port {start_port}"
    expected_port = start_port
    for index, port in enumerate(service_ports):
        assert port["port"] == expected_port, (
            f"{id}.port[{index}]['port'] isn't {expected_port} ({start_port} to {end_port})"
        )
        assert port["targetPort"] == expected_port, (
            f"{id}.port[{index}]['targetPort'] isn't {expected_port} ({start_port} to {end_port})"
        )
        assert port["nodePort"] == expected_port, (
            f"{id}.port[{index}]['nodePort'] isn't {expected_port} ({start_port} to {end_port})"
        )
        assert port["name"] == f"rtc-udp-{expected_port}", (
            f"{id}.port[{index}]['name'] isn't rtc-udp-{expected_port} ({start_port} to {end_port})"
        )
        expected_port += 1
    assert port["port"] == end_port, f"{id} doesn't end with port {end_port}"


@pytest.mark.parametrize("values_file", ["matrix-rtc-exposed-services-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_udp_range_services_are_sharded(values, make_templates):
    start_port = 32000

    services = await get_sfu_udp_port_range_services(start_port, start_port, values, make_templates)
    assert len(services) == 1, "SFU UDP Range service is incorrectly sharded for 1 port"
    assert_sharded_udp_range_ports(start_port, start_port, services[0])

    services = await get_sfu_udp_port_range_services(start_port, start_port + 1, values, make_templates)
    assert len(services) == 1, "SFU UDP Range service is incorrectly sharded for 2 ports"
    assert_sharded_udp_range_ports(start_port, start_port + 1, services[0])

    services = await get_sfu_udp_port_range_services(start_port, start_port + 249, values, make_templates)
    assert len(services) == 1, "SFU UDP Range service is incorrectly sharded for 250 ports"
    assert_sharded_udp_range_ports(start_port, start_port + 249, services[0])

    services = await get_sfu_udp_port_range_services(start_port, start_port + 250, values, make_templates)
    assert len(services) == 2, "SFU UDP Range service is incorrectly sharded for 251 ports"
    assert_sharded_udp_range_ports(start_port, start_port + 249, services[0])
    assert_sharded_udp_range_ports(start_port + 250, start_port + 250, services[1])

    services = await get_sfu_udp_port_range_services(start_port, start_port + 999, values, make_templates)
    assert len(services) == 4, "SFU UDP Range service is incorrectly sharded for 1000 ports"
    assert_sharded_udp_range_ports(start_port, start_port + 249, services[0])
    assert_sharded_udp_range_ports(start_port + 250, start_port + 499, services[1])
    assert_sharded_udp_range_ports(start_port + 500, start_port + 749, services[2])
    assert_sharded_udp_range_ports(start_port + 750, start_port + 999, services[3])
