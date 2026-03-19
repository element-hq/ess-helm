# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import ipaddress
import itertools
import re

import pytest
import yaml

from . import (
    DeployableDetails,
    PropertyType,
    all_deployables_details,
    services_values_files_to_test,
    values_files_to_test,
)
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_port_and_type(values, make_templates):
    """
    Exposed services port types must correctly configure Kubernetes Services.

    When Helm values specify exposed services with different port types:
    - NodePort: Services must have type=NodePort with valid nodePort integers
    - HostPort: Deployments must have hostPort configured, no Service exposure
    - LoadBalancer: Services must have type=LoadBalancer
    - DynamicNodePort: Services must have type=NodePort with empty nodePort for dynamic allocation
    """
    num_of_expected_ports = {}
    num_of_expected_exposed_services = {}

    def exposed_service_mode(deployable_details: DeployableDetails, mode: str):
        nonlocal num_of_expected_ports
        nonlocal num_of_expected_exposed_services
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        test_annotations_labels = {
            "exposed-service-port-type": mode,
        }
        exposed_services_values = dict(exposed_services)
        for service_name in exposed_services:
            # "dynamic node port" is NodePort mode with nodePort set to empty in the value file
            # this will make kubernetes allocate a nodePort dynamically
            if mode == "DynamicNodePort":
                if "portRange" in exposed_services_values[service_name]:
                    exposed_services_values[service_name]["portRange"]["nodePort"] = ""
                else:
                    exposed_services_values[service_name]["nodePort"] = ""

            exposed_services_values[service_name]["portType"] = mode.replace("Dynamic", "")
            exposed_services_values[service_name]["annotations"] = test_annotations_labels
            num_of_expected_exposed_services[deployable_details.name] += 1
            if "portRange" in exposed_services_values[service_name]:
                num_of_expected_ports[deployable_details.name] += (
                    exposed_services_values[service_name]["portRange"]["endPort"]
                    - exposed_services_values[service_name]["portRange"]["startPort"]
                )
            else:
                num_of_expected_ports[deployable_details.name] += 1
        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)
        deployable_details.set_helm_values(values, PropertyType.Labels, test_annotations_labels)

    found_exposed_services = {}
    found_services = {}
    for service_mode in ("NodePort", "HostPort", "LoadBalancer", "DynamicNodePort"):
        for deployable_details in all_deployables_details:
            num_of_expected_ports[deployable_details.name] = 0
            num_of_expected_exposed_services[deployable_details.name] = 0

        for deployable_details in all_deployables_details:
            found_exposed_services[deployable_details.name] = []
            found_services[deployable_details.name] = []

        iterate_deployables_parts(
            lambda deployable_details, service_mode=service_mode: exposed_service_mode(
                deployable_details, service_mode
            ),
            lambda deployable_details: deployable_details.has_exposed_services,
        )
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_exposed_services:
                if template["kind"] == "Service":
                    found_services[deployable_details.name].append(template)
                    if "exposed-service-port-type" in template["metadata"].get("annotations", {}):
                        for port in template["spec"]["ports"]:
                            if template["metadata"]["annotations"]["exposed-service-port-type"] == "DynamicNodePort":
                                assert template["spec"]["type"] == "NodePort"
                                assert "nodePort" not in port, f"Found nodePort despite using {service_mode}: {port}"
                            elif template["metadata"]["annotations"]["exposed-service-port-type"] == "NodePort":
                                assert template["spec"]["type"] == "NodePort"
                                assert "nodePort" in port, f"`nodePort` is missing despite using {service_mode}: {port}"
                                assert int(port["nodePort"]), (
                                    f"`nodePort` is not an integer despite using {service_mode}: {port}"
                                )
                            else:
                                assert (
                                    template["spec"]["type"]
                                    == template["metadata"]["annotations"]["exposed-service-port-type"]
                                )
                        found_exposed_services[deployable_details.name].append(template)
                if template["kind"] == "Deployment" and "exposed-service-port-type" in template["metadata"]["labels"]:
                    container = template["spec"]["template"]["spec"]["containers"][0]
                    for port in container["ports"]:
                        if service_mode != "HostPort":
                            assert "hostPort" not in port, f"Found hostPort despite using {service_mode}: {port}"
                    if service_mode == "HostPort":
                        assert num_of_expected_ports[deployable_details.name] == len(
                            [p for p in container["ports"] if "hostPort" in p]
                        ), (
                            f"Found {num_of_expected_ports[deployable_details.name]} ports despite using {service_mode}"
                            f" : {container}"
                        )

        for deployable_details in all_deployables_details:
            if service_mode == "HostPort":
                assert len(found_exposed_services[deployable_details.name]) == 0, (
                    f"Expected no exposed services when using HostPort mode for {deployable_details.name}, "
                    f"but found {len(found_exposed_services[deployable_details.name])} services: "
                    f"{[template_id(s) for s in found_exposed_services[deployable_details.name]]}"
                )
            else:
                assert (
                    len(found_exposed_services[deployable_details.name])
                    == num_of_expected_exposed_services[deployable_details.name]
                ), (
                    f"Exposed service count mismatch for {deployable_details.name} in {service_mode} mode: "
                    f"Expected {num_of_expected_exposed_services[deployable_details.name]} services, "
                    f"found {len(found_exposed_services[deployable_details.name])}: "
                    f"{[template_id(s) for s in found_exposed_services[deployable_details.name]]}"
                )


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_external_ips(values, make_templates):
    """
    Exposed services must properly configure externalIPs in generated Services.

    When Helm values configure externalIPs for exposed services, generated Services
    must include the configured externalIPs in spec.externalIPs.

    This enables external access to services via the specified IP addresses.
    """
    # we set deployables external ips on 10.0.X.1
    # and each exposed services increments the last digit of the ip
    expected_deployable_external_ips = {}
    num_of_expected_exposed_services = {}

    def exposed_external_ip(deployable_details: DeployableDetails, external_ip: ipaddress.IPv4Address):
        nonlocal num_of_expected_exposed_services
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        exposed_services_values = dict(exposed_services)
        for service_name in exposed_services:
            exposed_services_values[service_name]["annotations"] = {
                "exposed-service-external-ip": str(external_ip),
            }
            exposed_services_values[service_name]["externalIPs"] = ("127.0.0.1", str(external_ip))
            external_ip += 1
            num_of_expected_exposed_services[deployable_details.name] += 1
        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)

    found_exposed_services = {}
    found_services = {}
    next_external_ip = ipaddress.IPv4Address("10.0.0.1")
    for deployable_details in all_deployables_details:
        expected_deployable_external_ips[deployable_details.name] = next_external_ip
        next_external_ip += 256
        num_of_expected_exposed_services[deployable_details.name] = 0
        found_exposed_services[deployable_details.name] = []
        found_services[deployable_details.name] = []

    iterate_deployables_parts(
        lambda deployable_details: exposed_external_ip(
            deployable_details, expected_deployable_external_ips[deployable_details.name]
        ),
        lambda deployable_details: deployable_details.has_exposed_services,
    )
    for template in await make_templates(values):
        deployable_details = template_to_deployable_details(template)
        if deployable_details.has_exposed_services and template["kind"] == "Service":
            found_services[deployable_details.name].append(template)
            if "exposed-service-external-ip" in template["metadata"].get("annotations", {}):
                found_exposed_services[deployable_details.name].append(template)
                assert template["spec"].get("externalIPs") == (
                    "127.0.0.1",
                    template["metadata"]["annotations"]["exposed-service-external-ip"],
                ), (
                    f"{template_id(template)} : Expected external IP "
                    f"{template['metadata']['annotations']['exposed-service-external-ip']}"
                )

    for deployable_details in all_deployables_details:
        assert (
            len(found_exposed_services[deployable_details.name])
            == num_of_expected_exposed_services[deployable_details.name]
        ), (
            f"Service count mismatch for {deployable_details.name} with external IPs: "
            f"Expected {num_of_expected_exposed_services[deployable_details.name]} services with external IPs, "
            f"found {len(found_exposed_services[deployable_details.name])}: "
            f"{[template_id(s) for s in found_exposed_services[deployable_details.name]]}"
        )


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_certificate(values, make_templates):
    """
    Exposed services with domains must properly configure TLS certificates.

    When exposed services have domains (indicating they require TLS):
    - With cert-manager configured: Helm must generate Certificate resources referencing the correct issuer
    - Without cert-manager: Services must use tlsSecret for TLS termination
    - Certificate resources must match the service domain and use the configured issuer

    This ensures proper TLS configuration for exposed services.
    """
    num_of_expected_certificates = {}

    def exposed_service_certificate(deployable_details: DeployableDetails, issuer_name: str):
        nonlocal num_of_expected_certificates
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        test_annotations = {
            "exposed-service-cert-manager": issuer_name,
        }
        exposed_services_values = dict(exposed_services)

        for service_name in exposed_services:
            if exposed_services_values[service_name].get("domain"):
                if issuer_name == "no-issuer":
                    exposed_services_values[service_name]["tlsSecret"] = f"{deployable_details.name}-tls-secret"
                else:
                    if exposed_services_values[service_name].get("tlsSecret"):
                        exposed_services_values[service_name].pop("tlsSecret")
                    num_of_expected_certificates[deployable_details.name] += 1
                exposed_services_values[service_name]["annotations"] = test_annotations

        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)

    found_exposed_services_using_cert_manager = {}
    found_certificates = {}

    values.setdefault("certManager", {})

    for cert_manager in ({"clusterIssuer": "cluster-issuer"}, {"issuer": "issuer"}, {}):
        values["certManager"] = cert_manager
        for deployable_details in all_deployables_details:
            found_exposed_services_using_cert_manager[deployable_details.name] = []
            num_of_expected_certificates[deployable_details.name] = 0
            found_certificates[deployable_details.name] = []

        issuer_name = "no-issuer"
        if cert_manager:
            issuer_name = list(cert_manager.values())[0]
        iterate_deployables_parts(
            lambda deployable_details, issuer_name=issuer_name: exposed_service_certificate(
                deployable_details, issuer_name
            ),
            lambda deployable_details: deployable_details.has_exposed_services,
        )
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_exposed_services:
                test_annotation_value = template["kind"] == "Service" and template["metadata"].get(
                    "annotations", {}
                ).get("exposed-service-cert-manager")
                if test_annotation_value and test_annotation_value != "no-issuer":
                    found_exposed_services_using_cert_manager[deployable_details.name].append(template)
                if template["kind"] == "Certificate":
                    found_certificates[deployable_details.name].append(template)
                    assert template["spec"]["issuerRef"]["name"] == issuer_name
                    kind = list(cert_manager.keys())[0]
                    assert template["spec"]["issuerRef"]["kind"] == kind[0].upper() + kind[1:]

        for deployable_details in all_deployables_details:
            assert num_of_expected_certificates[deployable_details.name] == len(
                found_certificates[deployable_details.name]
            ), (
                f"Certificate count mismatch for {deployable_details.name} with cert-manager {issuer_name}: "
                f"Expected {num_of_expected_certificates[deployable_details.name]} certificates, "
                f"found {len(found_certificates[deployable_details.name])}: "
                f"{[template_id(c) for c in found_certificates[deployable_details.name]]}"
            )
            if deployable_details.has_exposed_services:
                assert len(found_certificates[deployable_details.name]) == len(
                    found_exposed_services_using_cert_manager[deployable_details.name]
                ), (
                    f"Certificate count mismatch for {deployable_details.name} with cert-manager {issuer_name}: "
                    f"Found {len(found_certificates[deployable_details.name])} certificates but "
                    f"{len(found_exposed_services_using_cert_manager[deployable_details.name])} "
                    f"services using cert-manager: "
                    f"Certificates: {[template_id(c) for c in found_certificates[deployable_details.name]]}"
                )


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_traffic_policy(values, make_templates):
    """
    Exposed services must configure proper traffic routing policies.

    When Helm values specify traffic policies for exposed services:
    - Services must set spec.internalTrafficPolicy to the configured value (Local/Cluster)
    - Services must set spec.externalTrafficPolicy to the configured value (Local/Cluster)

    These policies control how Kubernetes routes internal and external traffic to service endpoints,
    impacting performance, network hops, and source IP preservation.
    """
    num_of_expected_exposed_services = {}

    def exposed_services_traffic_policy(deployable_details: DeployableDetails, internal: str, external: str):
        nonlocal num_of_expected_exposed_services
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        exposed_services_values = dict(exposed_services)
        test_annotations = {
            "exposed-service-internal": internal,
            "exposed-service-external": external,
        }
        for service_name in exposed_services_values:
            exposed_services_values[service_name]["internalTrafficPolicy"] = internal
            exposed_services_values[service_name]["externalTrafficPolicy"] = external
            exposed_services_values[service_name]["annotations"] = test_annotations
        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)

    found_exposed_services = {}
    found_services = {}
    traffic_policies = ("Local", "Cluster")
    for internal, external in list(itertools.product(traffic_policies, traffic_policies)):
        for deployable_details in all_deployables_details:
            num_of_expected_exposed_services[deployable_details.name] = 0

        for deployable_details in all_deployables_details:
            found_exposed_services[deployable_details.name] = []
            found_services[deployable_details.name] = []

        iterate_deployables_parts(
            lambda deployable_details, internal=internal, external=external: exposed_services_traffic_policy(
                deployable_details, internal, external
            ),
            lambda deployable_details: deployable_details.has_exposed_services,
        )
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_exposed_services and template["kind"] == "Service":
                found_services[deployable_details.name].append(template)
                if "exposed-service-internal" in template["metadata"].get("annotations", {}):
                    assert (
                        template["spec"].get("internalTrafficPolicy")
                        == template["metadata"]["annotations"]["exposed-service-internal"]
                    )
                    assert (
                        template["spec"].get("externalTrafficPolicy")
                        == template["metadata"]["annotations"]["exposed-service-external"]
                    )
        for deployable_details in all_deployables_details:
            assert (
                len(found_exposed_services[deployable_details.name])
                == num_of_expected_exposed_services[deployable_details.name]
            ), (
                f"Traffic policy count mismatch for {deployable_details.name}: "
                f"Expected {num_of_expected_exposed_services[deployable_details.name]} services with traffic policies, "
                f"found {len(found_exposed_services[deployable_details.name])}: "
                f"{[template_id(s) for s in found_services[deployable_details.name]]}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_services_are_named(templates):
    """
    Service ports must have unique, meaningful names.

    All ports in Kubernetes Services must have a 'name' field and unique names
    within each Service resource.
    """
    for template in templates:
        if template["kind"] == "Service":
            port_names = []
            for port in template["spec"]["ports"]:
                assert "name" in port, (
                    f"{template_id(template)} port {port.get('port', 'unknown')} is missing required 'name' field. "
                    f"Port definition: {port}"
                )
                port_names.append(port["name"])
            assert len(port_names) == len(set(port_names)), (
                f"Port names are not unique in {template_id(template)}: {port_names}. "
                f"Each port must have a distinct name."
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_are_valid_numbers_and_unique(templates):
    """
    Service ports must be unique.

    All ports in Kubernetes Services must have unique port numbers within each Service.
    """
    for template in templates:
        if template["kind"] == "Service":
            ports = []
            nodes_ports = []
            for port in template["spec"]["ports"]:
                assert int(port["port"]), (
                    f"{template_id(template)} port {port.get('name', 'unnamed')} has "
                    f"invalid port number: {port['port']}. "
                    f"Port must be a valid integer."
                )
                if port.get("nodePort"):
                    assert int(port["nodePort"]), (
                        f"{template_id(template)} port {port.get('name', 'unnamed')} "
                        f"has invalid nodePort number: {port['nodePort']}. "
                        f"NodePort must be a valid integer."
                    )
                ports.append(port["port"])
                if port.get("nodePort"):
                    nodes_ports.append(port["nodePort"])
            assert len(template["spec"]["ports"]) == len(set(ports)), (
                f"Port numbers are not unique in {template_id(template)}: {ports}. "
                f"Each port in a service must have a distinct port number."
            )
            if nodes_ports:
                assert len(template["spec"]["ports"]) == len(set(nodes_ports)), (
                    f"NodePort numbers are not unique in {template_id(template)}: {nodes_ports}. "
                    f"Each NodePort must have a distinct port number."
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_not_too_many_ports_in_services(templates):
    """
    Services must have a valid number of ports within Kubernetes limits.

    All Kubernetes Services generated by this Helm chart must:
    - Define a ports specification
    - Have at least one port
    - Not exceed 250 ports (Kubernetes hard limit)

    This prevents invalid configurations that would be rejected by the Kubernetes API.
    """
    for template in templates:
        if template["kind"] == "Service":
            assert "ports" in template["spec"], (
                f"{template_id(template)} is missing required 'ports' specification. "
                f"Every service must define at least one port."
            )

            number_of_ports = len(template["spec"]["ports"])
            assert number_of_ports > 0, (
                f"{template_id(template)} has no ports defined. Services must specify at least one port."
            )
            assert number_of_ports <= 250, (
                f"{template_id(template)} has {number_of_ports} ports, exceeding Kubernetes limit of 250. "
                f"Consider splitting this service or using fewer ports."
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_references_to_services_are_anchored_by_the_cluster_domain(values, make_templates):
    """
    Service references must use proper cluster domain anchoring.

    All .svc references in Helm templates must be fully qualified with:
    - The cluster domain (cluster.local. by default)
    - Or the configured custom clusterDomain if specified

    Proper FQDN formatting (service.namespace.svc.cluster.local.) ensures reliable
    DNS resolution and service-to-service communication within Kubernetes.
    """
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.cluster.local." in line, (
                    f"{template_id(template)} contains service reference that isn't properly anchored: {line=}. "
                    f"Expected '.svc.cluster.local.' but found '{line.strip()}'. "
                    f"Service references must be fully qualified with the cluster domain."
                )

    values["clusterDomain"] = "k8s.example.com."
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.k8s.example.com." in line, (
                    f"{template_id(template)} contains service reference that doesn't use "
                    f"configured cluster domain: {line=}. "
                    f"Expected '.svc.k8s.example.com.' but found '{line.strip()}'. "
                    f"Service references must use the configured clusterDomain: k8s.example.com."
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_references_to_services_exist(namespace: str, templates: list[dict]) -> None:
    """
    All service references must point to existing services.

    Every .svc.cluster.local. reference in Helm templates must correspond to:
    - A Service resource that exists in the same chart
    - A properly formatted FQDN (service.namespace.svc.cluster.local.)

    This prevents runtime failures caused by references to non-existent services
    that would only be discovered during Kubernetes deployment.
    """
    services_names_fqdns = []

    templates_containing_services: dict[str, list[str]] = {}
    for template in templates:
        if template["kind"] == "Service":
            services_names_fqdns.append(f"{template['metadata']['name']}.{namespace}.svc.cluster.local.")
        else:
            template_as_yaml = yaml.dump(template)
            for line in template_as_yaml.splitlines():
                if ".svc.cluster.local." in line:
                    matches = re.findall(r"[^\.\s\"\'@/]+\.[^\.]+\.svc\.cluster\.local\.", line)
                    assert len(matches) > 0, (
                        f"Found service reference {line.strip()} but couldn't extract service name. "
                        f"Expected format: service.namespace.svc.cluster.local."
                    )
                    templates_containing_services.setdefault(template_id(template), []).extend(matches)
    for id, referenced_services in templates_containing_services.items():
        for referenced_service in referenced_services:
            assert referenced_service in services_names_fqdns, (
                f"{id} refers to non-existent service '{referenced_service}'. "
                f"Available services: {sorted(services_names_fqdns)}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_services_are_dual_stack_where_possible(templates):
    """
    Services must prefer dual-stack networking.

    All Kubernetes Services must set spec.ipFamilyPolicy: PreferDualStack to enable
    both IPv4 and IPv6 connectivity when available.
    """
    for template in templates:
        if template["kind"] == "Service":
            assert template["spec"]["ipFamilyPolicy"] == "PreferDualStack", (
                f"{template_id(template)} has ipFamilyPolicy '{template['spec']['ipFamilyPolicy']}' "
                "instead of 'PreferDualStack'. "
                f"Services should prefer dual-stack networking for better compatibility."
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_services_specify_type_by_default(templates):
    """
    Services must have explicit types and valid configuration.

    All Kubernetes Services must:
    - Have an explicit spec.type (ClusterIP or NodePort)
    - ClusterIP services: must not have externalTrafficPolicy (only valid for LoadBalancer/NodePort)
    - NodePort services: must have externalTrafficPolicy and no explicit clusterIP
    - Must not have externalIPs unless explicitly configured

    This ensures proper Kubernetes service behavior and network routing.
    """
    for template in templates:
        if template["kind"] == "Service":
            # Default service type is ClusterIP for internal services
            # Or NodePort for exposed services
            service_type = template["spec"].get("type")
            assert service_type in ("ClusterIP", "NodePort"), (
                f"{template_id(template)} has invalid service type '{service_type}'. "
                f"Expected 'ClusterIP' or 'NodePort'."
            )
            if template["spec"]["type"] == "ClusterIP":
                assert "externalTrafficPolicy" not in template["spec"], (
                    f"{template_id(template)} has externalTrafficPolicy defined for ClusterIP service. "
                    f"externalTrafficPolicy is only valid for NodePort/LoadBalancer services."
                )
            else:
                assert "clusterIP" not in template["spec"], (
                    f"{template_id(template)} has clusterIP defined for NodePort service. "
                    f"NodePort services should not explicitly set clusterIP."
                )
                assert "externalTrafficPolicy" in template["spec"], (
                    f"{template_id(template)} is missing required externalTrafficPolicy "
                    f"for NodePort service. NodePort services must specify traffic routing policy."
                )
            assert "externalIPs" not in template["spec"], (
                f"{template_id(template)} has externalIPs defined but no external IPs were configured. "
                f"Remove externalIPs field or configure external IPs in values."
            )
