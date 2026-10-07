# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import base64

import pyhelm3
import pytest
import yaml

from .utils import PERSISTENT_WORKLOAD_KINDS, template_id


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
            assert tcp_port == 30001
            break
    else:
        raise RuntimeError("Could not find config-overrides.yaml")


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_invalid_yaml_in_matrix_rtc_sfu_additional_fails(values, make_templates):
    values["matrixRTC"].setdefault("sfu", {})["additional"] = {"invalid.yaml": {"config": "not yaml"}}

    with pytest.raises(
        pyhelm3.errors.FailedToRenderChartError, match="matrixRTC.sfu.additional\\['invalid.yaml'\\] is invalid"
    ):
        await make_templates(values)


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
        if template["kind"] in PERSISTENT_WORKLOAD_KINDS and "matrix-rtc-sfu" in template["metadata"]["name"]:
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
        if template["kind"] in PERSISTENT_WORKLOAD_KINDS and "matrix-rtc-sfu" in template["metadata"]["name"]:
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
        if template["kind"] in PERSISTENT_WORKLOAD_KINDS and "matrix-rtc-sfu" in template["metadata"]["name"]:
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


def get_template(templates, kind, name):
    for template in templates:
        if template["kind"] == kind and template["metadata"]["name"] == name:
            return template
    raise AssertionError(f"{kind}/{name} not found")


def authorisation_service_env(templates, release_name):
    deployment = get_template(templates, "Deployment", f"{release_name}-matrix-rtc-authorisation-service")
    return {env["name"]: env.get("value") for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]}


def synapse_homeserver_overrides(templates, configmap_name):
    return yaml.safe_load(get_template(templates, "ConfigMap", configmap_name)["data"]["04-homeserver-overrides.yaml"])


def init_secrets_requested(templates, release_name):
    for template in templates:
        if template["kind"] == "Job" and template["metadata"]["name"] == f"{release_name}-init-secrets":
            return template["spec"]["template"]["spec"]["containers"][0]["args"][2].split(",")
    return []


@pytest.mark.parametrize("values_file", ["example-default-enabled-components-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_is_generated_and_loaded_by_synapse(release_name, namespace, values, templates):
    assert (
        f"{release_name}-generated:MATRIX_RTC_REGISTRATION:registration:/registration-templates/matrix-rtc-registration.yaml"
        in init_secrets_requested(templates, release_name)
    )

    registration = yaml.safe_load(
        get_template(templates, "ConfigMap", f"{release_name}-init-secrets")["data"]["matrix-rtc-registration.yaml"]
    )
    assert registration["as_token"] == "${AS_TOKEN}"
    assert registration["hs_token"] == "${HS_TOKEN}"
    assert registration["sender_localpart"] == "_lk_jwt_service"
    assert registration["url"] is None
    assert registration["namespaces"] == {"users": [{"exclusive": False, "regex": f"@.*:{values['serverName']}"}]}
    assert registration["io.element.msc4502.scopes"] == ["urn:matrix:client:io.element.msc4502:rooms:is_joined"]
    assert registration["io.element.msc4512.proxy_prefix"] == "rtc/livekit"
    assert registration["io.element.msc4512.proxy_url"] == (
        f"http://{release_name}-matrix-rtc-authorisation-service.{namespace}.svc.cluster.local.:8080"
    )
    # The proxy_url must target the authorisation service port
    service = get_template(templates, "Service", f"{release_name}-matrix-rtc-authorisation-service")
    assert {"name": "http", "port": 8080, "targetPort": "http"} in service["spec"]["ports"]

    registration_path = f"/secrets/{release_name}-generated/MATRIX_RTC_REGISTRATION"
    for configmap_name in [f"{release_name}-synapse", f"{release_name}-synapse-hook"]:
        homeserver_overrides = synapse_homeserver_overrides(templates, configmap_name)
        assert registration_path in homeserver_overrides["app_service_config_files"]
        assert homeserver_overrides["experimental_features"]["msc4502_enabled"] is True
        assert homeserver_overrides["experimental_features"]["msc4512_enabled"] is True

    env = authorisation_service_env(templates, release_name)
    assert env["LIVEKIT_AS_REGISTRATION_FILE"] == registration_path
    assert env["LIVEKIT_HS_SERVER_NAME"] == values["serverName"]
    # Still needed for the routes that are not proxied by Synapse
    assert "LIVEKIT_FULL_ACCESS_HOMESERVERS" in env
    assert "LIVEKIT_CS_API_URL_OVERRIDES" in env


@pytest.mark.parametrize("values_file", ["example-default-enabled-components-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_sender_localpart_is_configurable(release_name, values, make_templates):
    values["matrixRTC"].setdefault("user", {})["localpart"] = "rtc-appservice"

    templates = await make_templates(values)
    registration = yaml.safe_load(
        get_template(templates, "ConfigMap", f"{release_name}-init-secrets")["data"]["matrix-rtc-registration.yaml"]
    )
    assert registration["sender_localpart"] == "rtc-appservice"


@pytest.mark.parametrize("values_file", ["synapse-matrix-rtc-secrets-externally-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_from_external_secret(release_name, values, make_templates):
    values["initSecrets"] = {"enabled": True}
    templates = await make_templates(values)

    assert not any("MATRIX_RTC_REGISTRATION" in secret for secret in init_secrets_requested(templates, release_name))
    for template in templates:
        if template["kind"] == "ConfigMap" and template["metadata"]["name"] == f"{release_name}-init-secrets":
            assert "matrix-rtc-registration.yaml" not in template["data"]

    registration_path = f"/secrets/{release_name}-matrix-rtc-external-registration/registration.yaml"
    for configmap_name in [f"{release_name}-synapse", f"{release_name}-synapse-hook"]:
        assert registration_path in synapse_homeserver_overrides(templates, configmap_name)["app_service_config_files"]
    assert authorisation_service_env(templates, release_name)["LIVEKIT_AS_REGISTRATION_FILE"] == registration_path


@pytest.mark.parametrize("values_file", ["synapse-matrix-rtc-secrets-in-helm-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_from_helm_values(release_name, namespace, templates):
    for secret_name in [
        f"{release_name}-matrix-rtc-authorisation-service",
        f"{release_name}-matrix-rtc-authorisation-service-pre",
    ]:
        secret = get_template(templates, "Secret", secret_name)
        # The registration provided in the values is templated
        registration = yaml.safe_load(base64.b64decode(secret["data"]["REGISTRATION"]).decode("utf-8"))
        assert registration["io.element.msc4512.proxy_url"] == (
            f"http://{release_name}-matrix-rtc-authorisation-service.{namespace}.svc.cluster.local.:8080"
        )

    registration_path = f"/secrets/{release_name}-matrix-rtc-authorisation-service/REGISTRATION"
    homeserver_overrides = synapse_homeserver_overrides(templates, f"{release_name}-synapse")
    assert registration_path in homeserver_overrides["app_service_config_files"]
    assert authorisation_service_env(templates, release_name)["LIVEKIT_AS_REGISTRATION_FILE"] == registration_path

    # The check-config hook runs before the non-hook Secret exists
    hook_registration_path = f"/secrets/{release_name}-matrix-rtc-authorisation-service-pre/REGISTRATION"
    hook_homeserver_overrides = synapse_homeserver_overrides(templates, f"{release_name}-synapse-hook")
    assert hook_registration_path in hook_homeserver_overrides["app_service_config_files"]


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_server_name_is_required(values, make_templates):
    del values["serverName"]
    with pytest.raises(
        pyhelm3.errors.FailedToRenderChartError, match="serverName is required when matrixRTC.enabled=true"
    ):
        await make_templates(values)


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_is_generated_without_synapse(release_name, values, make_templates):
    values["serverName"] = "remote.example.com"
    templates = await make_templates(values)

    # The registration is generated for the homeserver, which isn't deployed by the chart, to load it
    assert (
        f"{release_name}-generated:MATRIX_RTC_REGISTRATION:registration:/registration-templates/matrix-rtc-registration.yaml"
        in init_secrets_requested(templates, release_name)
    )
    registration = yaml.safe_load(
        get_template(templates, "ConfigMap", f"{release_name}-init-secrets")["data"]["matrix-rtc-registration.yaml"]
    )
    assert registration["namespaces"] == {"users": [{"exclusive": False, "regex": "@.*:remote.example.com"}]}

    env = authorisation_service_env(templates, release_name)
    assert env["LIVEKIT_AS_REGISTRATION_FILE"] == f"/secrets/{release_name}-generated/MATRIX_RTC_REGISTRATION"
    assert env["LIVEKIT_HS_SERVER_NAME"] == "remote.example.com"


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_registration_without_synapse(release_name, values, make_templates):
    values["matrixRTC"]["appserviceRegistration"] = {
        "secret": "{{ $.Release.Name }}-matrix-rtc-external-registration",
        "secretKey": "registration.yaml",
    }
    values["serverName"] = "remote.example.com"
    templates = await make_templates(values)
    env = authorisation_service_env(templates, release_name)
    assert (
        env["LIVEKIT_AS_REGISTRATION_FILE"]
        == f"/secrets/{release_name}-matrix-rtc-external-registration/registration.yaml"
    )
    assert env["LIVEKIT_HS_SERVER_NAME"] == "remote.example.com"
