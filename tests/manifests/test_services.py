# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

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
async def test_exposed_services_configurability(values, make_templates):
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
            exposed_services_values[service_name]["portType"] = mode
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
    for service_mode in ("NodePort", "HostPort", "LoadBalancer"):
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
                        assert (
                            template["spec"]["type"] == template["metadata"]["annotations"]["exposed-service-port-type"]
                        )
                        found_exposed_services[deployable_details.name].append(template)
                if template["kind"] == "Deployment" and "exposed-service-port-type" in template["metadata"]["labels"]:
                    container = template["spec"]["template"]["spec"]["containers"][0]
                    for port in container["ports"]:
                        if service_mode != "HostPort":
                            assert "hostPort" not in port, f"Found hostPort despite using {service_mode} : {port}"
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
                    f"Found exposed service despite using HostPort : {found_exposed_services}"
                )
            else:
                assert (
                    len(found_exposed_services[deployable_details.name])
                    == num_of_expected_exposed_services[deployable_details.name]
                ), f"Did not find expected exposed service despite using {service_mode}. Services: {found_services}"


@pytest.mark.parametrize("values_file", services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_exposed_services_certificate(values, make_templates):
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
                f"Did not find number of expected certificates : {found_certificates[deployable_details.name]}"
                f" when testing with cert-manager {issuer_name}"
            )
            if deployable_details.has_exposed_services:
                assert len(found_certificates[deployable_details.name]) == len(
                    found_exposed_services_using_cert_manager[deployable_details.name]
                ), (
                    f"Did not find expected certificates : {found_certificates[deployable_details.name]}"
                    f" when testing with cert-manager {issuer_name}"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ports_in_services_are_named(templates):
    for template in templates:
        if template["kind"] == "Service":
            port_names = []
            for port in template["spec"]["ports"]:
                assert "name" in port, f"{template_id(template)} has a port without a name: {port}"
                port_names.append(port["name"])
            assert len(port_names) == len(set(port_names)), (
                f"Port names are not unique: {template_id(template)}, {port_names}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_not_too_many_ports_in_services(templates):
    for template in templates:
        if template["kind"] == "Service":
            assert "ports" in template["spec"], f"{template_id(template)} does not specify a ports list"

            number_of_ports = len(template["spec"]["ports"])
            assert number_of_ports > 0, f"{template_id(template)} does not include any ports"
            assert number_of_ports <= 250, f"{template_id(template)} has more than 250 ports"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_references_to_services_are_anchored_by_the_cluster_domain(values, make_templates):
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.cluster.local." in line, (
                    f"{template_id(template)} has {line=} which has a reference to a Service that isn't "
                    "anchored with the default cluster domain"
                )

    values["clusterDomain"] = "k8s.example.com."
    for template in await make_templates(values):
        template_as_yaml = yaml.dump(template)
        for line in template_as_yaml.splitlines():
            if ".svc" in line:
                assert ".svc.k8s.example.com." in line, (
                    f"{template_id(template)} has {line=} which has a reference to a Service that isn't "
                    "anchored with the configured cluster domain"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_services_are_dual_stack_where_possible(templates):
    for template in templates:
        if template["kind"] == "Service":
            assert template["spec"]["ipFamilyPolicy"] == "PreferDualStack", (
                f"{template_id(template)} does not set ipFamilyPolicy to PreferDualStack"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_services_specify_type_by_default(templates):
    for template in templates:
        if template["kind"] == "Service":
            # Default service type is ClusterIP for internal services
            # Or NodePort for exposed services
            assert template["spec"].get("type") in ("ClusterIP", "NodePort"), (
                f"{template_id(template)} service type is not ClusterIP"
            )
            if template["spec"]["type"] != "ClusterIP":
                assert "clusterIP" not in template["spec"], (
                    f"{template_id(template)} has a clusterIP defined for a non-ClusterIP service"
                )
