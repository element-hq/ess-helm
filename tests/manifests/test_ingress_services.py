# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import ipaddress

import pytest

from . import (
    DeployableDetails,
    PropertyType,
    all_deployables_details,
    values_files_to_test,
)
from .utils import iterate_deployables_ingress_parts, template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_services_global_service_properties(values, make_templates):
    values.setdefault("ingress", {}).setdefault("service", {})["type"] = "LoadBalancer"
    values.setdefault("ingress", {}).setdefault("service", {})["internalTrafficPolicy"] = "Local"
    values.setdefault("ingress", {}).setdefault("service", {})["externalTrafficPolicy"] = "Local"
    values.setdefault("ingress", {}).setdefault("service", {})["annotations"] = {
        "global": "set",
    }
    templates = await make_templates(values)
    services_by_name = dict[str, dict]()
    for template in templates:
        if template["kind"] == "Service":
            services_by_name[template["metadata"]["name"]] = template

    for ingress in templates:
        if ingress["kind"] != "Ingress":
            continue
        for rule in ingress["spec"]["rules"]:
            for path in rule["http"]["paths"]:
                backend_service = path["backend"]["service"]
                assert backend_service["name"] in services_by_name, (
                    f"Backend service {backend_service['name']} not found in "
                    f"known services: {list(services_by_name.keys())}"
                )
                found_service = services_by_name[backend_service["name"]]
                assert "name" in backend_service["port"], (
                    f"{template_id(ingress)} : Backend service {backend_service['name']} is not targetting a port name"
                )
                port_names = [port["name"] for port in found_service["spec"]["ports"]]
                assert backend_service["port"]["name"] in port_names, (
                    f"Port name {backend_service['port']['name']} not found in service {backend_service['name']}"
                )
                assert found_service["spec"].get("type") == "LoadBalancer", (
                    f"Service {backend_service['name']} is not a LoadBalancer despite setting "
                    "$.ingress.service.type to LoadBalancer"
                )
                assert found_service["spec"].get("internalTrafficPolicy") == "Local", (
                    f"Service {backend_service['name']} does not use Local internalTrafficPolicy despite setting "
                    "$.ingress.service.internalTrafficPolicy to Local"
                )
                assert found_service["spec"].get("externalTrafficPolicy") == "Local", (
                    f"Service {backend_service['name']} does not use Local externalTrafficPolicy despite setting "
                    "$.ingress.service.externalTrafficPolicy to Local and $.ingress.service.type to LoadBalancer"
                )
                assert "annotations" in found_service["metadata"]
                assert "global" in found_service["metadata"]["annotations"]
                assert found_service["metadata"]["annotations"]["global"] == "set"
                assert "clusterIP" not in found_service["spec"], (
                    f"{template_id(template)} has a clusterIP defined for a non-ClusterIP service"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_merges_global_and_component_ingress_services_annotations(values, make_templates):
    def set_annotations(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.Ingress,
            {
                "service": {
                    "annotations": {
                        "component": "set",
                        "merged": "from_component",
                        "global": None,
                    }
                }
            },
        )

    iterate_deployables_ingress_parts(set_annotations)
    values.setdefault("ingress", {}).setdefault("service", {})["annotations"] = {
        "global": "set",
        "merged": "from_global",
    }

    templates = await make_templates(values)
    services_by_name = dict[str, dict]()
    for template in templates:
        if template["kind"] == "Service":
            services_by_name[template["metadata"]["name"]] = template

    for ingress in await make_templates(values):
        if ingress["kind"] != "Ingress":
            continue
        for rule in ingress["spec"]["rules"]:
            for path in rule["http"]["paths"]:
                backend_service = path["backend"]["service"]
                assert backend_service["name"] in services_by_name, (
                    f"Backend service {backend_service['name']} not found in "
                    f"known services: {list(services_by_name.keys())}"
                )
                found_service = services_by_name[backend_service["name"]]
                assert "annotations" in found_service["metadata"]
                assert "component" in found_service["metadata"]["annotations"]
                assert found_service["metadata"]["annotations"]["component"] == "set"

                assert "merged" in found_service["metadata"]["annotations"]
                assert found_service["metadata"]["annotations"]["merged"] == "from_component"

                # The key is still in the template but it renders as null (Python None)
                # And the k8s API will then filter it out
                assert "global" in found_service["metadata"]["annotations"]
                assert found_service["metadata"]["annotations"]["global"] is None


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_services_local_service_properties(values, make_templates):
    values.setdefault("ingress", {}).setdefault("service", {})["type"] = "ClusterIP"
    values.setdefault("ingress", {}).setdefault("service", {})["internalTrafficPolicy"] = "Cluster"
    values.setdefault("ingress", {}).setdefault("service", {})["externalTrafficPolicy"] = "Cluster"

    # we set deployables external ips on 10.0.X.1
    expected_deployable_external_ips = {}

    next_external_ip = ipaddress.IPv4Address("10.0.0.1")
    for deployable_details in all_deployables_details:
        if deployable_details.has_ingress:
            expected_deployable_external_ips.setdefault(deployable_details.name, next_external_ip)
            next_external_ip += 256

    def set_ingress_service_properties(deployable_details: DeployableDetails, external_ip: ipaddress.IPv4Address):
        deployable_details.set_helm_values(
            values,
            PropertyType.Ingress,
            {
                "service": {
                    "type": "LoadBalancer",
                    "internalTrafficPolicy": "Local",
                    "externalTrafficPolicy": "Local",
                    "externalIPs": ("127.0.0.1", str(external_ip)),
                    "annotations": {
                        "ingress-service-external-ip": str(external_ip),
                    },
                },
            },
        )

    iterate_deployables_ingress_parts(
        lambda deployable_details: set_ingress_service_properties(
            deployable_details, expected_deployable_external_ips[deployable_details.name]
        )
    )

    templates = await make_templates(values)
    for template in templates:
        services_by_name = dict[str, dict]()
        for template in templates:
            if template["kind"] == "Service":
                services_by_name[template["metadata"]["name"]] = template

    for ingress in templates:
        if ingress["kind"] != "Ingress":
            continue
        for rule in ingress["spec"]["rules"]:
            for path in rule["http"]["paths"]:
                backend_service = path["backend"]["service"]
                assert backend_service["name"] in services_by_name, (
                    f"Backend service {backend_service['name']} not found in "
                    f"known services: {list(services_by_name.keys())}"
                )
                found_service = services_by_name[backend_service["name"]]
                assert "name" in backend_service["port"], (
                    f"{template_id(ingress)} : Backend service {backend_service['name']} is not targetting a port name"
                )
                port_names = [port["name"] for port in found_service["spec"]["ports"]]
                assert backend_service["port"]["name"] in port_names, (
                    f"Port name {backend_service['port']['name']} not found in service {backend_service['name']}"
                )
                assert found_service["spec"].get("type") == "LoadBalancer", (
                    f"Service {backend_service['name']} is not a LoadBalancer despite setting "
                    ".ingress.service.type to LoadBalancer"
                )
                assert found_service["spec"].get("internalTrafficPolicy") == "Local", (
                    f"Service {backend_service['name']} does not use Local internalTrafficPolicy despite setting "
                    ".ingress.service.internalTrafficPolicy to Local"
                )
                assert found_service["spec"].get("externalTrafficPolicy") == "Local", (
                    f"Service {backend_service['name']} does not use Local externalTrafficPolicy despite setting "
                    "$.ingress.service.externalTrafficPolicy to Local and $.ingress.service.type to LoadBalancer"
                )
                assert found_service["spec"].get("externalIPs") == (
                    "127.0.0.1",
                    found_service["metadata"]["annotations"]["ingress-service-external-ip"],
                ), (
                    f"Service {backend_service['name']} does not have externalIPs set despite externalIPs set to "
                    f"{services_by_name[backend_service['name']]['metadata']['annotations']['ingress-service-external-ip']})"
                )
                assert "clusterIP" not in found_service["spec"], (
                    f"{template_id(template)} has a clusterIP defined for a non-ClusterIP service"
                )
