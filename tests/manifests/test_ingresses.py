# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import (
    DeployableDetails,
    PropertyType,
    all_deployables_details,
    services_values_files_to_test,
    values_files_to_test,
)
from .utils import iterate_deployables_ingress_parts, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_has_ingress(templates):
    seen_deployables = set[DeployableDetails]()
    seen_deployables_with_ingresses = set[DeployableDetails]()

    for template in templates:
        deployable_details = template_to_deployable_details(template)
        seen_deployables.add(deployable_details)
        if template["kind"] == "Ingress":
            seen_deployables_with_ingresses.add(deployable_details)

    for seen_deployable in seen_deployables_with_ingresses:
        assert seen_deployable.has_ingress


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
            assert "rules" in template["spec"]
            assert len(template["spec"]["rules"]) > 0

            for rule in template["spec"]["rules"]:
                assert "host" in rule
                found_hosts.append(rule["host"])
    assert set(found_hosts) == set(expected_hosts)


@pytest.mark.parametrize("values_file", values_files_to_test)
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


@pytest.mark.parametrize("values_file", values_files_to_test - services_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingress_annotations_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "annotations" not in template["metadata"]


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_renders_component_ingress_annotations(values, make_templates):
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
            assert "annotations" in template["metadata"]
            assert "component" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["component"] == "set"


@pytest.mark.parametrize("values_file", values_files_to_test)
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


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_merges_global_and_component_ingress_annotations(values, make_templates):
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
            assert "annotations" in template["metadata"]
            assert "component" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["component"] == "set"

            assert "merged" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["merged"] == "from_component"

            # The key is still in the template but it renders as null (Python None)
            # And the k8s API will then filter it out
            assert "global" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["global"] is None


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_ingressClassName_by_default(templates):
    for template in templates:
        if template["kind"] == "Ingress":
            assert "ingressClassName" not in template["spec"]


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_component_ingressClassName(values, make_templates):
    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(set_ingress_className)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "component"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_global_ingressClassName(values, make_templates):
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "global"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_ingressClassName_beats_global(values, make_templates):
    def set_ingress_className(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"className": "component"})

    iterate_deployables_ingress_parts(set_ingress_className)
    values.setdefault("ingress", {})["className"] = "global"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "ingressClassName" in template["spec"]
            assert template["spec"]["ingressClassName"] == "component"
