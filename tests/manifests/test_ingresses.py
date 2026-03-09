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
    services_values_files_to_test,
    values_files_to_test,
)
from .utils import iterate_deployables_ingress_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_has_ingress(templates):
    """
    Ingress resources must be generated for deployables that support ingress.

    When a deployable has ingress support (has_ingress=True), the Helm chart must
    generate corresponding Ingress resources. This ensures all ingress-capable
    components are properly exposed via Kubernetes Ingress.
    """
    seen_deployables = set[DeployableDetails]()
    seen_deployables_with_ingresses = set[DeployableDetails]()

    for template in templates:
        deployable_details = template_to_deployable_details(template)
        seen_deployables.add(deployable_details)
        if template["kind"] == "Ingress":
            seen_deployables_with_ingresses.add(deployable_details)

    for seen_deployable in seen_deployables_with_ingresses:
        assert seen_deployable.has_ingress, (
            f"Deployable {seen_deployable.name} has Ingress resource but has_ingress is False"
        )


@pytest.mark.parametrize(
    "values_file",
    values_files_to_test
    # This is because MAS ingress is not deployed until it is ready to handle auth,
    # which has after syn2mas has been run successfully (dryRun false)
    - {
        "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-externally-values.yaml",
        "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-in-helm-values.yaml",
    },
)
@pytest.mark.asyncio_cooperative
async def test_ingress_is_expected_host(values, templates):
    """
    Ingress resources must use the expected hostnames from Helm values.

    When Helm values configure specific hostnames for ingress resources:
    - Ingress rules must use the exact hostnames specified in values
    - For well-known deployables, use serverName if no host is specified
    - All configured hosts must be present in generated Ingress resources

    This ensures proper DNS routing and hostname-based virtual hosting.
    """

    def get_hosts_from_fragment(values_fragment, deployable_details):
        if deployable_details.name == "well-known":
            if not values_fragment.get("host"):
                yield values["serverName"]
            else:
                yield values_fragment["host"]
        else:
            yield values_fragment["host"]

    def get_hosts():
        for deployable_details in all_deployables_details:
            if deployable_details.has_ingress and deployable_details.get_helm_values(
                values, PropertyType.Enabled, default_value=False
            ):
                yield from get_hosts_from_fragment(
                    deployable_details.get_helm_values(values, PropertyType.Ingress), deployable_details
                )

    expected_hosts = get_hosts()

    found_hosts = []
    for template in templates:
        if template["kind"] == "Ingress":
            assert "rules" in template["spec"], f"{template_id(template)} is missing required 'rules' specification"
            assert len(template["spec"]["rules"]) > 0, (
                f"{template_id(template)} has no rules defined. Ingress must have at least one rule."
            )

            for rule in template["spec"]["rules"]:
                assert "host" in rule, f"{template_id(template)} rule is missing required 'host' field: {rule}"
                found_hosts.append(rule["host"])
    assert set(found_hosts) == set(expected_hosts), (
        f"Host mismatch: Expected {sorted(set(expected_hosts))}, found {sorted(set(found_hosts))}"
    )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_paths_are_all_prefix(templates):
    """
    Ingress paths must use Prefix pathType for proper path-based routing.

    All HTTP paths in Ingress resources must use pathType: Prefix to ensure
    consistent path matching behavior across different ingress controllers.
    ImplementationSpecific pathType is unacceptable as we want to be ingress-controller agnostic
    and only use Kubernetes-standard options.

    This ensures reliable path-based routing and compatibility with various ingress controllers.
    """
    for template in templates:
        if template["kind"] == "Ingress":
            assert "rules" in template["spec"], f"{template_id(template)} is missing required 'rules' specification"
            assert len(template["spec"]["rules"]) > 0, (
                f"{template_id(template)} has no rules defined. Ingress must have at least one rule."
            )

            for rule in template["spec"]["rules"]:
                assert "http" in rule, f"{template_id(template)} rule is missing required 'http' specification: {rule}"
                assert "paths" in rule["http"], (
                    f"{template_id(template)} rule is missing required 'paths' specification: {rule}"
                )
                for path in rule["http"]["paths"]:
                    assert "pathType" in path, f"{template_id(template)} path is missing required 'pathType': {path}"

                    # Exact would be ok, but ImplementationSpecifc is unacceptable as we don't know the implementation
                    assert path["pathType"] == "Prefix", (
                        f"{template_id(template)} path uses pathType '{path['pathType']}' instead of 'Prefix': {path}"
                    )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_annotations_by_default(templates):
    """
    Ingress resources must not have annotations by default.

    When no specific annotations are configured in Helm values, Ingress resources
    should not include an annotations field. This ensures clean default configurations
    and prevents unexpected behavior from unspecified annotations.
    """
    for template in templates:
        if template["kind"] == "Ingress":
            assert "annotations" not in template["metadata"], (
                f"{template_id(template)} has annotations but none were configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_renders_component_ingress_annotations(values, make_templates):
    """
    Ingress resources must render component-specific annotations.

    When Helm values configure annotations at the component level (per-deployable),
    the generated Ingress resources must include those annotations in their metadata.
    This allows fine-grained control over ingress behavior per component.
    """

    def set_annotations(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.Ingress,
            {
                "annotations": {
                    "component": "set",
                }
            },
        )

    iterate_deployables_ingress_parts(set_annotations)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"], (
                f"{template_id(template)} is missing annotations despite component annotations being configured"
            )
            assert "component" in template["metadata"]["annotations"], (
                f"{template_id(template)} is missing 'component' annotation: {template['metadata']['annotations']}"
            )
            assert template["metadata"]["annotations"]["component"] == "set", (
                f"{template_id(template)} has incorrect component annotation value: "
                f"{template['metadata']['annotations']['component']}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_renders_global_ingress_annotations(values, make_templates):
    """
    Ingress resources must render global annotations.

    When Helm values configure annotations at the global level ($.ingress.annotations),
    all generated Ingress resources must include those annotations in their metadata.
    This allows chart-wide control over ingress behavior.
    """
    values.setdefault("ingress", {})["annotations"] = {
        "global": "set",
    }

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"], (
                f"{template_id(template)} is missing annotations despite global annotations being configured"
            )
            assert "global" in template["metadata"]["annotations"], (
                f"{template_id(template)} is missing 'global' annotation: {template['metadata']['annotations']}"
            )
            assert template["metadata"]["annotations"]["global"] == "set", (
                f"{template_id(template)} has incorrect global annotation value: "
                f"{template['metadata']['annotations']['global']}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_merges_global_and_component_ingress_annotations(values, make_templates):
    """
    Ingress resources must properly merge global and component annotations.

    When both global ($.ingress.annotations) and component-level annotations are configured:
    - Component annotations take precedence over global annotations
    - Component annotations with null values should override global annotations
      (expecting to delete the global annotation from the component annotation)
    - All annotations should be properly merged in the final Ingress metadata

    This ensures proper annotation precedence and merging behavior.
    """

    def set_annotations(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values,
            PropertyType.Ingress,
            {
                "annotations": {
                    "component": "set",
                    "merged": "from_component",
                    "global": None,
                }
            },
        )

    iterate_deployables_ingress_parts(set_annotations)
    values.setdefault("ingress", {})["annotations"] = {
        "global": "set",
        "merged": "from_global",
    }

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"], (
                f"{template_id(template)} is missing annotations despite both global and"
                "component annotations being configured"
            )
            assert "component" in template["metadata"]["annotations"], (
                f"{template_id(template)} is missing 'component' annotation: {template['metadata']['annotations']}"
            )
            assert template["metadata"]["annotations"]["component"] == "set", (
                f"{template_id(template)} has incorrect component annotation value: "
                f"{template['metadata']['annotations']['component']}"
            )

            assert "merged" in template["metadata"]["annotations"], (
                f"{template_id(template)} is missing 'merged' annotation: {template['metadata']['annotations']}"
            )
            assert template["metadata"]["annotations"]["merged"] == "from_component", (
                f"{template_id(template)} has incorrect merged annotation value (should be from component): "
                f"{template['metadata']['annotations']['merged']}"
            )

            # The key is still in the template but it renders as null (Python None)
            # And the k8s API will then filter it out
            assert "global" in template["metadata"]["annotations"], (
                f"{template_id(template)} is missing 'global' annotation: {template['metadata']['annotations']}"
            )
            assert template["metadata"]["annotations"]["global"] is None, (
                f"{template_id(template)} has incorrect global annotation value (should be None/null): "
                f"{template['metadata']['annotations']['global']}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_global(make_templates, values):
    """
    Ingress resources must not include TLS configuration when TLS is disabled globally.

    When $.ingress.tlsEnabled is set to false, no Ingress resources should include
    TLS configuration in their spec.
    """
    values.setdefault("ingress", {})["tlsEnabled"] = False
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"], (
                f"{template_id(template)} has TLS configuration despite global tlsEnabled being false"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_beats_global(make_templates, values):
    """
    Component-level TLS disabled setting must override global TLS enabled setting.

    When a component specifically sets tlsEnabled: false, it should override any
    global $.ingress.tlsEnabled: true setting. This allows per-component control over TLS.
    """

    def set_tls_disabled(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsEnabled": False})

    iterate_deployables_ingress_parts(set_tls_disabled)
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"], (
                f"{template_id(template)} has TLS configuration despite component tlsEnabled being false"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingress_tlsSecret(values, make_templates):
    """
    Ingress resources must use component-specific TLS secrets when configured.

    When a component sets a specific tlsSecret in its ingress configuration,
    the generated Ingress must use that secret name in its TLS configuration.
    This allows per-component TLS certificate management.
    """

    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"], (
                f"{template_id(template)} is missing TLS configuration despite component tlsSecret being set"
            )
            assert len(template["spec"]["tls"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'])} TLS configurations, expected only 1"
            )
            assert len(template["spec"]["tls"][0]["hosts"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'][0]['hosts'])} TLS hosts, expected only 1"
            )
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"], (
                f"{template_id(template)} TLS host {template['spec']['tls'][0]['hosts'][0]} "
                f"does not match ingress host {template['spec']['rules'][0]['host']}"
            )
            assert template["spec"]["tls"][0]["secretName"] == "component", (
                f"{template_id(template)} TLS secretName is {template['spec']['tls'][0]['secretName']}, "
                "expected 'component'"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_global_ingress_tlsSecret(values, make_templates):
    """
    Ingress resources must use global TLS secrets when no component-specific secret is configured.

    When $.ingress.tlsSecret is set globally and no component-specific tlsSecret is configured,
    all Ingress resources must use the global TLS secret name in their TLS configuration.
    This allows chart-wide TLS certificate management.
    """
    values.setdefault("ingress", {})["tlsSecret"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"], (
                f"{template_id(template)} is missing TLS configuration despite global tlsSecret being set"
            )
            assert len(template["spec"]["tls"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'])} TLS configurations, expected only 1"
            )
            assert len(template["spec"]["tls"][0]["hosts"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'][0]['hosts'])} TLS hosts, expected only 1"
            )
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"], (
                f"{template_id(template)} TLS host {template['spec']['tls'][0]['hosts'][0]} "
                f"does not match ingress host {template['spec']['rules'][0]['host']}"
            )
            assert template["spec"]["tls"][0]["secretName"] == "global", (
                f"{template_id(template)} TLS secretName is {template['spec']['tls'][0]['secretName']}, "
                "expected 'global'"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_ingress_tlsSecret_beats_global(values, make_templates):
    """
    Component-specific TLS secrets must override global TLS secrets.

    When both global ($.ingress.tlsSecret) and component-specific tlsSecret are configured,
    the component-specific secret must take precedence. This allows per-component override
    of chart-wide TLS certificate settings.
    """

    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)
    values.setdefault("ingress", {})["tlsSecret"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"], (
                f"{template_id(template)} is missing TLS configuration despite both "
                "global and component tlsSecret being set"
            )
            assert len(template["spec"]["tls"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'])} TLS configurations, expected only 1"
            )
            assert len(template["spec"]["tls"][0]["hosts"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'][0]['hosts'])} TLS hosts, expected only 1"
            )
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"], (
                f"{template_id(template)} TLS host {template['spec']['tls'][0]['hosts'][0]} "
                f"does not match ingress host {template['spec']['rules'][0]['host']}"
            )
            assert template["spec"]["tls"][0]["secretName"] == "component", (
                f"{template_id(template)} TLS secretName is {template['spec']['tls'][0]['secretName']}, "
                f"expected 'component' (component should override global 'global')"
            )


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_tls_no_secretName_by_default(templates):
    """
    TLS configurations must not include secretName by default when using cert-manager.

    When cert-manager is configured and no explicit tlsSecret is set, TLS configurations
    should not include a secretName field. cert-manager will automatically create and manage
    the TLS secret based on the configured issuer.
    """
    for template in templates:
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"], f"{template_id(template)} is missing TLS configuration"
            for tls_spec in template["spec"]["tls"]:
                assert "secretName" not in tls_spec, (
                    f"{template_id(template)} TLS configuration has secretName {tls_spec.get('secretName')}, "
                    f"but no explicit tlsSecret was configured (cert-manager should manage this)"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingressClassName_by_default(templates):
    """
    Ingress resources must not have ingressClassName by default.

    When no specific ingress class is configured, Ingress resources should not include
    an ingressClassName field. This allows the default ingress controller to handle
    the ingress resources according to cluster configuration.
    """
    for template in templates:
        if template["kind"] == "Ingress":
            assert "ingressClassName" not in template["spec"], (
                f"{template_id(template)} has ingressClassName {template['spec'].get('ingressClassName')}, "
                f"but no ingress class was configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingressClassName(values, make_templates):
    """
    Ingress resources must use component-specific ingress class names when configured.

    When a component sets a specific className in its ingress configuration,
    the generated Ingress must use that class name in its spec.ingressClassName field.
    This allows per-component selection of ingress controllers.
    """

    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(set_ingress_className)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"], (
                f"{template_id(template)} is missing ingressClassName despite component className being configured"
            )
            assert template["spec"]["ingressClassName"] == "component", (
                f"{template_id(template)} ingressClassName is {template['spec']['ingressClassName']}, "
                "expected 'component'"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_global_ingressClassName(values, make_templates):
    """
    Ingress resources must use global ingress class names when no component-specific class is configured.

    When $.ingress.className is set globally and no component-specific className is configured,
    all Ingress resources must use the global class name in their spec.ingressClassName field.
    This allows chart-wide selection of ingress controllers.
    """
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"], (
                f"{template_id(template)} is missing ingressClassName despite global className being configured"
            )
            assert template["spec"]["ingressClassName"] == "global", (
                f"{template_id(template)} ingressClassName is {template['spec']['ingressClassName']}, expected 'global'"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_ingressClassName_beats_global(values, make_templates):
    """
    Component-specific ingress class names must override global ingress class names.

    When both global ($.ingress.className) and component-specific className are configured,
    the component-specific class name must take precedence. This allows per-component override
    of chart-wide ingress controller selection.
    """

    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(set_ingress_className)
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"], (
                f"{template_id(template)} is missing ingressClassName despite both "
                "global and component className being configured"
            )
            assert template["spec"]["ingressClassName"] == "component", (
                f"{template_id(template)} ingressClassName is {template['spec']['ingressClassName']}, "
                f"expected 'component' (component should override global 'global')"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_services_global_service_properties(values, make_templates):
    """
    Ingress backend services must use global service properties when configured.

    When global ingress service properties are configured ($.ingress.service.*):
    - Backend services must use the specified service type (LoadBalancer)
    - Services must apply the configured traffic policies (internalTrafficPolicy, externalTrafficPolicy)
    - Services must include global annotations
    - Services must target named ports

    This ensures consistent service configuration across all ingress-backed services.
    """
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
    """
    Ingress backend services must properly merge global and component service annotations.

    When both global ($.ingress.service.annotations) and component-level service annotations are configured:
    - Component annotations take precedence over global annotations
    - Component annotations with null values should override global annotations
    - All annotations should be properly merged in the final Service metadata

    This ensures proper annotation precedence and merging behavior for ingress backend services.
    """

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
    """
    Ingress backend services must use component-specific service properties when configured.

    When component-specific ingress service properties are configured:
    - Component properties must override global properties
    - Services must use the specified service type (LoadBalancer)
    - Services must apply the configured traffic policies
    - Services must include component-specific externalIPs
    - Services must include component-specific annotations

    This ensures per-component control over ingress backend service configuration.
    """
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


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_certManager_clusterissuer(make_templates, values):
    """
    Ingress resources must include cert-manager cluster issuer annotations when configured.

    When certManager.clusterIssuer is configured:
    - Ingress resources must include cert-manager.io/cluster-issuer annotation
    - The annotation must reference the configured cluster issuer name
    - TLS configuration must use the expected secret name format for cert-manager

    This enables automatic TLS certificate provisioning via cert-manager using cluster issuers.
    """
    values["certManager"] = {"clusterIssuer": "cluster-issuer-name"}
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "cert-manager.io/cluster-issuer" in template["metadata"]["annotations"], (
                f"Ingress {template['name']} does not have cert-manager annotation"
            )
            assert template["metadata"]["annotations"]["cert-manager.io/cluster-issuer"] == "cluster-issuer-name"
            assert template["spec"]["tls"][0]["secretName"] == f"{template['metadata']['name']}-certmanager-tls", (
                f"Ingress {template['metadata']['name']} does not have correct secret name for cert-manager tls"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_certManager_issuer(make_templates, values):
    """
    Ingress resources must include cert-manager issuer annotations when configured.

    When certManager.issuer is configured:
    - Ingress resources must include cert-manager.io/issuer annotation
    - The annotation must reference the configured issuer name
    - TLS configuration must use the expected secret name format for cert-manager

    This enables automatic TLS certificate provisioning via cert-manager using namespace issuers.
    """
    values["certManager"] = {"issuer": "issuer-name"}
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "cert-manager.io/issuer" in template["metadata"]["annotations"], (
                f"Ingress {template['name']} does not have cert-manager annotation"
            )
            assert template["metadata"]["annotations"]["cert-manager.io/issuer"] == "issuer-name"
            assert template["spec"]["tls"][0]["secretName"] == f"{template['metadata']['name']}-certmanager-tls", (
                f"Ingress {template['metadata']['name']} does not have correct secret name for cert-manager tls"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_ingress_tlsSecret_beats_certManager(values, make_templates):
    """
    Component-specific TLS secrets must override cert-manager configuration.

    When both certManager is configured and a component sets a specific tlsSecret:
    - The component-specific tlsSecret must be used
    - No cert-manager annotations should be present
    - The TLS configuration must use the component-specific secret name

    This allows manual TLS certificate management to override automatic cert-manager provisioning.
    """

    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)
    values["certManager"] = {"issuer": "issuer-name"}

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"], (
                f"{template_id(template)} is missing TLS configuration despite component tlsSecret being set"
            )
            assert len(template["spec"]["tls"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'])} TLS configurations, expected only 1"
            )
            assert len(template["spec"]["tls"][0]["hosts"]) == 1, (
                f"{template_id(template)} has {len(template['spec']['tls'][0]['hosts'])} TLS hosts, expected only 1"
            )
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"], (
                f"{template_id(template)} TLS host {template['spec']['tls'][0]['hosts'][0]} "
                f"does not match ingress host {template['spec']['rules'][0]['host']}"
            )
            assert template["spec"]["tls"][0]["secretName"] == "component", (
                f"{template_id(template)} TLS secretName is {template['spec']['tls'][0]['secretName']}, "
                "expected 'component'"
            )
            assert not template["metadata"].get("annotations"), (
                f"{template_id(template)} has cert-manager annotations despite component tlsSecret being set: "
                f"{template['metadata'].get('annotations')}"
            )
