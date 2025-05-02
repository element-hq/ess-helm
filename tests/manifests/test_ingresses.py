# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import DeployableDetails, PropertyType, values_files_to_test, values_files_with_ingresses
from .utils import iterate_deployables_ingress_parts


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_has_ingress(templates, template_to_deployable_details):
    seen_deployables = set[DeployableDetails]()
    seen_deployables_with_ingresses = set[DeployableDetails]()

    for template in templates:
        deployable_details = template_to_deployable_details(template)
        seen_deployables.add(deployable_details)
        if template["kind"] == "Ingress":
            seen_deployables_with_ingresses.add(deployable_details)

    for seen_deployable in seen_deployables_with_ingresses:
        assert seen_deployable.has_ingress


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_ingress_is_expected_host(deployables_details, values, templates):
    def get_hosts_from_fragment(values_fragment, deployable_details):
        if deployable_details.name == "well-known":
            if not values_fragment.get("host"):
                yield values["serverName"]
            else:
                yield values_fragment["host"]
        else:
            yield values_fragment["host"]

    def get_hosts():
        for deployable_details in deployables_details:
            if deployable_details.has_ingress:
                yield from get_hosts_from_fragment(
                    deployable_details.get_helm_values(values, PropertyType.Ingress), deployable_details
                )

    expected_hosts = get_hosts()

    found_hosts = []
    for template in templates:
        if template["kind"] == "Ingress":
            assert "rules" in template["spec"]
            assert len(template["spec"]["rules"]) > 0

            for rule in template["spec"]["rules"]:
                assert "host" in rule
                found_hosts.append(rule["host"])
    assert set(found_hosts) == set(expected_hosts)


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_ingress_paths_are_all_prefix(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "rules" in template["spec"]
            assert len(template["spec"]["rules"]) > 0

            for rule in template["spec"]["rules"]:
                assert "http" in rule
                assert "paths" in rule["http"]
                for path in rule["http"]["paths"]:
                    assert "pathType" in path

                    # Exact would be ok, but ImplementationSpecifc is unacceptable as we don't know the implementation
                    assert path["pathType"] == "Prefix"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_annotations_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "annotations" not in template["metadata"]


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_renders_component_ingress_annotations(deployables_details, values, make_templates):
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

    iterate_deployables_ingress_parts(deployables_details, set_annotations)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"]
            assert "component" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["component"] == "set"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_renders_global_ingress_annotations(values, make_templates):
    values.setdefault("ingress", {})["annotations"] = {
        "global": "set",
    }

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"]
            assert "global" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["global"] == "set"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_merges_global_and_component_ingress_annotations(deployables_details, values, make_templates):
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

    iterate_deployables_ingress_parts(deployables_details, set_annotations)
    values.setdefault("ingress", {})["annotations"] = {
        "global": "set",
        "merged": "from_global",
    }

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "annotations" in template["metadata"]
            assert "component" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["component"] == "set"

            assert "merged" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["merged"] == "from_component"

            # The key is still in the template but it renders as null (Python None)
            # And the k8s API will then filter it out
            assert "global" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["global"] is None


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_global(make_templates, values):
    values.setdefault("ingress", {})["tlsEnabled"] = False
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_beats_global(make_templates, values, deployables_details):
    def set_tls_disabled(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsEnabled": False})

    iterate_deployables_ingress_parts(deployables_details, set_tls_disabled)
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingress_tlsSecret(deployables_details, values, make_templates):
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(deployables_details, set_tls_secret)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_uses_global_ingress_tlsSecret(values, make_templates):
    values.setdefault("ingress", {})["tlsSecret"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "global"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_component_ingress_tlsSecret_beats_global(deployables_details, values, make_templates):
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(deployables_details, set_tls_secret)
    values.setdefault("ingress", {})["tlsSecret"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_tls_no_secretName_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            for tls_spec in template["spec"]["tls"]:
                assert "secretName" not in tls_spec


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_no_ingressClassName_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "ingressClassName" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingressClassName(deployables_details, values, make_templates):
    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(deployables_details, set_ingress_className)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "component"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_uses_global_ingressClassName(values, make_templates):
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "global"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_component_ingressClassName_beats_global(deployables_details, values, make_templates):
    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(deployables_details, set_ingress_className)
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "component"


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_ingress_services(templates):
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
                if backend_service["port"].get("name"):
                    port_names = [port["name"] for port in found_service["spec"]["ports"]]
                    assert backend_service["port"]["name"] in port_names, (
                        f"Port name {backend_service['port']['name']} not found in service {backend_service['name']}"
                    )
                else:
                    port_numbers = [port["port"] for port in found_service["spec"]["ports"]]
                    assert backend_service["port"]["number"] in port_numbers, (
                        f"Port number {backend_service['port']['number']} "
                        f"not found in service {backend_service['name']}"
                    )


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_ingress_certManager_clusterissuer(make_templates, values):
    values.setdefault("certManager", {})["clusterIssuer"] = "cluster-issuer-name"
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "cert-manager.io/cluster-issuer" in template["metadata"]["annotations"], (
                f"Ingress {template['name']} does not have cert-manager annotation"
            )
            assert template["metadata"]["annotations"]["cert-manager.io/cluster-issuer"] == "cluster-issuer-name"
            assert template["spec"]["tls"][0]["secretName"] == f"{template['metadata']['name']}-certmanager-tls", (
                f"Ingress {template['metadata']['name']} does not have correct secret name for cert-manager tls"
            )


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_ingress_certManager_issuer(make_templates, values):
    values.setdefault("certManager", {})["issuer"] = "issuer-name"
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "cert-manager.io/issuer" in template["metadata"]["annotations"], (
                f"Ingress {template['name']} does not have cert-manager annotation"
            )
            assert template["metadata"]["annotations"]["cert-manager.io/issuer"] == "issuer-name"
            assert template["spec"]["tls"][0]["secretName"] == f"{template['metadata']['name']}-certmanager-tls", (
                f"Ingress {template['metadata']['name']} does not have correct secret name for cert-manager tls"
            )


@pytest.mark.parametrize("values_file", values_files_with_ingresses)
@pytest.mark.asyncio_cooperative
async def test_component_ingress_tlsSecret_beats_certManager(deployables_details, values, make_templates):
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(deployables_details, set_tls_secret)
    values.setdefault("certManager", {})["issuer"] = "issuer-name"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"
            assert not template["metadata"].get("annotations")
