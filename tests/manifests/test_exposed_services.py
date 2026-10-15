# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import ipaddress
import itertools

import pytest

from . import (
    DeployableDetails,
    PropertyType,
    all_deployables_details,
    services_values_files_to_test,
)
from .utils import (
    PERSISTENT_WORKLOAD_KINDS,
    iterate_deployables_parts,
    template_id,
    template_to_deployable_details,
)


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_port_and_type(values, make_templates):
    """
    Exposed services port types must correctly configure Kubernetes Services.

    When Helm values specify exposed services with different port types:
    - NodePort: Services must have type=NodePort with valid nodePort integers
    - HostPort: Deployments must have hostPort configured, no Service exposure
    - LoadBalancer: Services must have type=LoadBalancer
    - ClusterIP: Services must have type=ClusterIP
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
    for service_mode in ("NodePort", "HostPort", "LoadBalancer", "ClusterIP", "DynamicNodePort"):
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
                if (
                    template["kind"] in PERSISTENT_WORKLOAD_KINDS
                    and "exposed-service-port-type" in template["metadata"]["labels"]
                ):
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
                    if template["spec"]["type"] != "ClusterIP":
                        assert (
                            template["spec"].get("externalTrafficPolicy")
                            == template["metadata"]["annotations"]["exposed-service-external"]
                        )
                    else:
                        assert "externalTrafficPolicy" not in template["spec"]
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


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_ip_family(values, make_templates):
    """
    Exposed services must configure the IP family of their Services.

    When Helm values specify an ipFamily for exposed services:
    - ipv4: Services must set spec.ipFamilies to [IPv4] and spec.ipFamilyPolicy to SingleStack
    - ipv6: Services must set spec.ipFamilies to [IPv6] and spec.ipFamilyPolicy to SingleStack
    - dual-stack: Services must set spec.ipFamilies to [IPv4, IPv6] and spec.ipFamilyPolicy to PreferDualStack

    Leaving ipFamily unset keeps the historical chart behaviour of preferring dual-stack
    without specifying ipFamilies, which is asserted by test_services_are_dual_stack_where_possible.
    """
    num_of_expected_exposed_services = {}

    def exposed_services_ip_family(deployable_details: DeployableDetails, ip_family: str):
        nonlocal num_of_expected_exposed_services
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        exposed_services_values = dict(exposed_services)
        test_annotations = {
            "exposed-service-ip-family": ip_family,
        }
        for service_name in exposed_services_values:
            exposed_services_values[service_name]["ipFamily"] = ip_family
            exposed_services_values[service_name]["annotations"] = test_annotations
            num_of_expected_exposed_services[deployable_details.name] += 1
        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)

    found_exposed_services = {}
    found_services = {}
    for ip_family in ("ipv4", "ipv6", "dual-stack"):
        for deployable_details in all_deployables_details:
            num_of_expected_exposed_services[deployable_details.name] = 0

        for deployable_details in all_deployables_details:
            found_exposed_services[deployable_details.name] = []
            found_services[deployable_details.name] = []

        iterate_deployables_parts(
            lambda deployable_details, ip_family=ip_family: exposed_services_ip_family(deployable_details, ip_family),
            lambda deployable_details: deployable_details.has_exposed_services,
        )
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_exposed_services and template["kind"] == "Service":
                found_services[deployable_details.name].append(template)
                if "exposed-service-ip-family" in template["metadata"].get("annotations", {}):
                    found_exposed_services[deployable_details.name].append(template)
                    if ip_family == "dual-stack":
                        expected_ip_families = ("IPv4", "IPv6")
                        assert template["spec"]["ipFamilyPolicy"] == "PreferDualStack", (
                            f"{template_id(template)} should prefer dual-stack but has "
                            f"ipFamilyPolicy '{template['spec']['ipFamilyPolicy']}'"
                        )
                    else:
                        expected_ip_families = ("IPv4",) if ip_family == "ipv4" else ("IPv6",)
                        assert template["spec"]["ipFamilyPolicy"] == "SingleStack", (
                            f"{template_id(template)} with ipFamily '{ip_family}' should be single stack but has "
                            f"ipFamilyPolicy '{template['spec']['ipFamilyPolicy']}'"
                        )
                    assert template["spec"]["ipFamilies"] == expected_ip_families, (
                        f"{template_id(template)} with ipFamily '{ip_family}' should have "
                        f"ipFamilies {expected_ip_families} but has {template['spec'].get('ipFamilies')}"
                    )

        for deployable_details in all_deployables_details:
            assert (
                len(found_exposed_services[deployable_details.name])
                == num_of_expected_exposed_services[deployable_details.name]
            ), (
                f"IP family count mismatch for {deployable_details.name} with ipFamily {ip_family}: "
                f"Expected {num_of_expected_exposed_services[deployable_details.name]} services with an IP family, "
                f"found {len(found_exposed_services[deployable_details.name])}: "
                f"{[template_id(s) for s in found_services[deployable_details.name]]}"
            )
