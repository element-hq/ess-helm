# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import (
    DeployableDetails,
    PropertyType,
    services_values_files_to_test,
    values_files_to_test,
)
from .utils import iterate_deployables_ingress_parts


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_global(make_templates, values):
    values.setdefault("ingress", {})["tlsEnabled"] = False
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_tlsSecret_beats_global(make_templates, values):
    def set_tls_disabled(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsEnabled": False})

    iterate_deployables_ingress_parts(set_tls_disabled)
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingress_tlsSecret(values, make_templates):
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
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


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_ingress_tlsSecret_beats_global(values, make_templates):
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)
    values.setdefault("ingress", {})["tlsSecret"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_tls_no_secretName_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            for tls_spec in template["spec"]["tls"]:
                assert "secretName" not in tls_spec


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ingress_certManager_clusterissuer(make_templates, values):
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
    def set_tls_secret(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"tlsSecret": "component"})

    iterate_deployables_ingress_parts(set_tls_secret)
    values["certManager"] = {"issuer": "issuer-name"}

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "tls" in template["spec"]
            assert len(template["spec"]["tls"]) == 1
            assert len(template["spec"]["tls"][0]["hosts"]) == 1
            assert template["spec"]["tls"][0]["hosts"][0] == template["spec"]["rules"][0]["host"]
            assert template["spec"]["tls"][0]["secretName"] == "component"
            assert not template["metadata"].get("annotations")
