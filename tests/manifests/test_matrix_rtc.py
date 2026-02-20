# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
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


@pytest.mark.parametrize("values_file", ["matrix-rtc-exposed-services-tls-values.yaml"])
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


@pytest.mark.parametrize("values_file", ["matrix-rtc-turn-tls-external-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_turn_tls_external_termination(values, templates):
    sfu_deployment = None
    sfu_configmap = None
    turn_tls_service = None

    for template in templates:
        if template["kind"] == "Deployment" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_deployment = template
        elif template["kind"] == "ConfigMap" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_configmap = template
        elif template["kind"] == "Service" and "turn-tls" in template["metadata"]["name"]:
            turn_tls_service = template
        if sfu_configmap and sfu_deployment and turn_tls_service:
            break

    assert sfu_deployment is not None, "SFU deployment not found"
    assert sfu_configmap is not None, "SFU configmap not found"
    assert turn_tls_service is not None, "TURN TLS service not found"

    # Verify TURN TLS service is created
    assert turn_tls_service["spec"]["ports"][0]["name"] == "turn-tls-tcp"
    assert turn_tls_service["spec"]["ports"][0]["port"] == 31002

    # Verify SFU deployment does NOT have turn-tls volume mounts (external termination)
    containers = sfu_deployment["spec"]["template"]["spec"]["containers"]
    sfu_container = next((c for c in containers if c["name"] == "sfu"), None)
    assert sfu_container is not None, "SFU container not found"

    volume_mounts = sfu_container.get("volumeMounts", [])
    turn_tls_mounts = [vm for vm in volume_mounts if "turn-tls" in vm.get("name", "")]
    assert len(turn_tls_mounts) == 0, "Found turn-tls volume mounts when they should not exist for external termination"

    config_data = sfu_configmap["data"]["config-overrides.yaml"]
    config_yaml = yaml.safe_load(config_data)

    assert "turn" in config_yaml, "No turn configuration found"
    turn_config = config_yaml["turn"]
    assert turn_config.get("enabled"), "TURN not enabled in config"
    assert "tls_port" in turn_config, "tls_port not found in turn config"
    assert "cert_file" not in turn_config, "cert_file should not exist for external termination"
    assert "key_file" not in turn_config, "key_file should not exist for external termination"


@pytest.mark.parametrize("values_file", ["matrix-rtc-turn-tls-external-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_turn_tls_external_termination_with_certmanager(values, make_templates):
    """Test that TURN TLS works with tlsTerminationOnPod=false even when certManager is enabled."""
    # Enable certManager in the values
    values["certManager"] = {"clusterIssuer": "test-issuer"}

    # Find the SFU deployment
    sfu_deployment = None
    sfu_configmap = None

    for template in await make_templates(values):
        if template["kind"] == "Deployment" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_deployment = template
        elif template["kind"] == "ConfigMap" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_configmap = template
        if sfu_configmap and sfu_deployment:
            break

    assert sfu_deployment is not None, "SFU deployment not found"
    assert sfu_configmap is not None, "SFU configmap not found"

    # Verify SFU deployment does NOT have turn-tls volume mounts (external termination)
    containers = sfu_deployment["spec"]["template"]["spec"]["containers"]
    sfu_container = next((c for c in containers if c["name"] == "sfu"), None)
    assert sfu_container is not None, "SFU container not found"

    volume_mounts = sfu_container.get("volumeMounts", [])
    turn_tls_mounts = [vm for vm in volume_mounts if "turn-tls" in vm.get("name", "")]
    assert len(turn_tls_mounts) == 0, (
        "Found turn-tls volume mounts when they should not exist for external termination with certManager"
    )

    config_data = sfu_configmap["data"]["config-overrides.yaml"]
    config_yaml = yaml.safe_load(config_data)

    assert "turn" in config_yaml, "No turn configuration found"
    turn_config = config_yaml["turn"]
    assert turn_config.get("enabled"), "TURN not enabled in config"
    assert "tls_port" in turn_config, "tls_port not found in turn config"
    assert "cert_file" not in turn_config, "cert_file should not exist for external termination with certManager"
    assert "key_file" not in turn_config, "key_file should not exist for external termination with certManager"


@pytest.mark.parametrize("values_file", ["matrix-rtc-exposed-services-tls-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_turn_tls_pod_termination_with_secret(values, templates):
    """Test that TURN TLS works with tlsTerminationOnPod=true (default) and manual secret."""

    # Find the SFU deployment
    sfu_deployment = None
    sfu_configmap = None

    for template in templates:
        if template["kind"] == "Deployment" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_deployment = template
        elif template["kind"] == "ConfigMap" and "matrix-rtc-sfu" in template["metadata"]["name"]:
            sfu_configmap = template
        if sfu_configmap and sfu_deployment:
            break

    assert sfu_deployment is not None, "SFU deployment not found"
    assert sfu_configmap is not None, "SFU configmap not found"

    # Verify SFU deployment HAS turn-tls volume mounts (pod termination)
    containers = sfu_deployment["spec"]["template"]["spec"]["containers"]
    sfu_container = next((c for c in containers if c["name"] == "sfu"), None)
    assert sfu_container is not None, "SFU container not found"

    volume_mounts = sfu_container.get("volumeMounts", [])
    turn_tls_mounts = [vm for vm in volume_mounts if "turn-tls" in vm.get("name", "")]
    assert len(turn_tls_mounts) == 2, (
        "Expected 2 turn-tls volume mounts (cert and key) for pod termination with manual secret"
    )

    config_data = sfu_configmap["data"]["config-overrides.yaml"]
    config_yaml = yaml.safe_load(config_data)

    assert "turn" in config_yaml, "No turn configuration found"
    turn_config = config_yaml["turn"]
    assert turn_config.get("enabled"), "TURN not enabled in config"
    assert "tls_port" in turn_config, "tls_port not found in turn config"
    assert "cert_file" in turn_config, "cert_file should exist for pod termination with manual secret"
    assert "key_file" in turn_config, "key_file should exist for pod termination with manual secret"
    assert turn_config["cert_file"] == "/turn-tls/tls.crt", "cert_file path incorrect"
    assert turn_config["key_file"] == "/turn-tls/tls.key", "key_file path incorrect"
