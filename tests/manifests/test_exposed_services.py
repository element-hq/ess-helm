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
    Exposed services must configure the IP family policy and families of their Services.

    - When ipFamilyPolicy is unset, Services must use PreferDualStack if networking.ipFamily
      is dual-stack, SingleStack otherwise.
    - When Helm values specify ipFamilyPolicy for exposed services,
      Services must set spec.ipFamilyPolicy to that value.
    - When Helm values also specify ipFamilies, Services must set spec.ipFamilies to that list.
    - When ipFamilies is unset, Services must not set spec.ipFamilies, so the cluster
      picks the families based on the ipFamilyPolicy.
    """
    num_of_expected_exposed_services = {}

    def exposed_services_ip_family(
        deployable_details: DeployableDetails, ip_family_policy: str | None, ip_families: tuple[str, ...] | None
    ):
        nonlocal num_of_expected_exposed_services
        exposed_services = deployable_details.get_helm_values(values, PropertyType.ExposedServices)
        assert exposed_services is not None
        exposed_services_values = dict(exposed_services)
        test_annotations = {
            "exposed-service-ip-family": f"{ip_family_policy}-{ip_families}",
        }
        for service_name in exposed_services_values:
            if ip_family_policy is not None:
                exposed_services_values[service_name]["ipFamilyPolicy"] = ip_family_policy
            if ip_families is not None:
                exposed_services_values[service_name]["ipFamilies"] = list(ip_families)
            exposed_services_values[service_name]["annotations"] = test_annotations
            num_of_expected_exposed_services[deployable_details.name] += 1
        deployable_details.set_helm_values(values, PropertyType.ExposedServices, exposed_services_values)

    found_exposed_services = {}
    found_services = {}
    # Cases with unset values must run first: set_helm_values merges values across iterations,
    # so once ipFamilyPolicy or ipFamilies has been set, later iterations cannot unset them.
    for networking_ip_family, ip_family_policy, ip_families in (
        ("dual-stack", None, None),
        ("ipv4", None, None),
        ("ipv6", None, None),
        ("dual-stack", "PreferDualStack", None),
        ("dual-stack", "SingleStack", ("IPv4",)),
        ("dual-stack", "SingleStack", ("IPv6",)),
        ("dual-stack", "RequireDualStack", ("IPv4", "IPv6")),
    ):
        values.setdefault("networking", {})["ipFamily"] = networking_ip_family
        if ip_family_policy is None:
            expected_ip_family_policy = "PreferDualStack" if networking_ip_family == "dual-stack" else "SingleStack"
        else:
            expected_ip_family_policy = ip_family_policy

        for deployable_details in all_deployables_details:
            num_of_expected_exposed_services[deployable_details.name] = 0

        for deployable_details in all_deployables_details:
            found_exposed_services[deployable_details.name] = []
            found_services[deployable_details.name] = []

        iterate_deployables_parts(
            lambda deployable_details, ip_family_policy=ip_family_policy, ip_families=ip_families: (
                exposed_services_ip_family(deployable_details, ip_family_policy, ip_families)
            ),
            lambda deployable_details: deployable_details.has_exposed_services,
        )
        for template in await make_templates(values):
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_exposed_services and template["kind"] == "Service":
                found_services[deployable_details.name].append(template)
                if "exposed-service-ip-family" in template["metadata"].get("annotations", {}):
                    found_exposed_services[deployable_details.name].append(template)
                    assert template["spec"]["ipFamilyPolicy"] == expected_ip_family_policy, (
                        f"{template_id(template)} should have ipFamilyPolicy '{expected_ip_family_policy}' but has "
                        f"ipFamilyPolicy '{template['spec']['ipFamilyPolicy']}'"
                    )
                    if ip_families is None:
                        assert "ipFamilies" not in template["spec"], (
                            f"{template_id(template)} with unset ipFamilies should not have "
                            f"ipFamilies but has {template['spec'].get('ipFamilies')}"
                        )
                    else:
                        assert tuple(template["spec"]["ipFamilies"]) == ip_families, (
                            f"{template_id(template)} should have ipFamilies {ip_families} "
                            f"but has {template['spec'].get('ipFamilies')}"
                        )

        for deployable_details in all_deployables_details:
            assert (
                len(found_exposed_services[deployable_details.name])
                == num_of_expected_exposed_services[deployable_details.name]
            ), (
                f"IP family count mismatch for {deployable_details.name} with ipFamilyPolicy {ip_family_policy}: "
                f"Expected {num_of_expected_exposed_services[deployable_details.name]} services with an IP family, "
                f"found {len(found_exposed_services[deployable_details.name])}: "
                f"{[template_id(s) for s in found_services[deployable_details.name]]}"
            )
