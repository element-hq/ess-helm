# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest
import yaml

from . import (
    values_files_to_test,
)
from .utils import (
    PERSISTENT_WORKLOAD_KINDS,
    iterate_pod_template,
    template_id,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_service_ports_match_container_port_protocols(templates):
    """
    Service ports must use the protocol of the container port they target.

    A Service matches its target container port by number or name only, so a container port declared with the wrong
    protocol goes unnoticed while traffic reaches it through a Service. With a `hostPort` however, the container port's
    protocol is what the node forwards, and traffic of the other protocol is dropped.
    """
    workloads = list(iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS))
    for service in templates:
        if service["kind"] != "Service" or not service["spec"].get("selector"):
            continue
        selector = service["spec"]["selector"]
        for workload in workloads:
            labels = workload.pod_template["metadata"].get("labels", {})
            if any(labels.get(key) != value for key, value in selector.items()):
                continue
            container_ports = [
                port for container in workload.pod_template["spec"]["containers"] for port in container.get("ports", [])
            ]
            for service_port in service["spec"]["ports"]:
                target = service_port.get("targetPort", service_port["port"])
                targeted = [port for port in container_ports if target in (port.get("name"), port["containerPort"])]
                if not targeted:
                    continue
                protocol = service_port.get("protocol", "TCP")
                assert any(port.get("protocol", "TCP") == protocol for port in targeted), (
                    f"{template_id(service)} port {service_port.get('name', target)} ({protocol}) targets "
                    f"{workload.manifest_id} container ports with other protocols: {targeted}"
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
async def test_references_to_services_are_anchored_by_the_cluster_domain(
    values, make_templates, release_name, namespace
):
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
            if f"://{release_name}-" in line:
                assert f".{namespace}.svc.cluster.local." in line, (
                    f"{template_id(template)} contains service reference that isn't properly anchored: {line=}. "
                    f"Expected '.{namespace}.svc.cluster.local.' but found '{line.strip()}'. "
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
                for port in template["spec"]["ports"]:
                    assert "nodePort" not in port, (
                        f"{template_id(template)} has nodePort set on a ClusterIP service port. "
                        f"nodePort is only valid for NodePort/LoadBalancer services."
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


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_publishNotReadyAddresses_only_on_appservice_services(templates):
    """
    Asserts that the only usage of Service.spec.publishNotReadyAddresses: true is for app services.

    Some app services do a dance where, as part of their startup sequence, they cause Synapse to make a
    request back to them. As they aren't fully started up a standard Service isn't publishing addresses
    for the app service yet, hence publishNotReadyAddresses: true. However we don't want to route any
    other traffic (HTTPS Ingress, Metrics), until the app service is fully started up.

    It does not assert the other side of the link: that all app services use publishNotReadyAddresses: true
    as this doesn't appear to be required for all app services at this time
    """
    for template in templates:
        if template["kind"] == "Service":
            if not template["spec"].get("publishNotReadyAddresses", False):
                continue

            assert len(template["spec"]["ports"]) == 1, (
                f"{template_id(template)} has publishNotReadyAddresses=True but has more ports than just 'appservice'"
            )
            assert template["spec"]["ports"][0]["name"] == "appservice", (
                f"{template_id(template)} is directing non-appservice traffic"
            )
