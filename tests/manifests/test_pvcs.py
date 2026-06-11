# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvcs_only_present_if_expected(templates):
    deployable_details_to_seen_pvcs = {}
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            deployable_details = template_to_deployable_details(template)
            deployable_details_to_seen_pvcs.setdefault(deployable_details, False)
        if template["kind"] == "PersistentVolumeClaim":
            deployable_details = template_to_deployable_details(template)
            deployable_details_to_seen_pvcs[deployable_details] = True

    for deployable_details, seen_pvcs in deployable_details_to_seen_pvcs.items():
        if deployable_details.name == "hookshot":
            pytest.skip("Hookshot have PVCs conditionally, so it wont be always consistent with has_storage")
        assert seen_pvcs == deployable_details.has_storage, (
            f"{deployable_details.name}: {seen_pvcs=} when expecting {deployable_details.has_storage}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvcs_marked_as_being_kept_on_helm_uninstall_by_default(templates):
    for template in templates:
        if template["kind"] == "PersistentVolumeClaim":
            assert "helm.sh/resource-policy" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_pvcs_can_be_marked_as_to_be_deleted_on_helm_uninstall(values, make_templates):
    values.setdefault("storage", {})["resourcePolicy"] = "delete"

    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            assert "helm.sh/resource-policy" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["helm.sh/resource-policy"] == "delete"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_individual_pvcs_can_be_marked_as_to_be_deleted_on_helm_uninstall(values, make_templates):
    values.setdefault("storage", {})["resourcePolicy"] = "keep"
    iterate_deployables_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Storage, {"resourcePolicy": "delete"}
        ),
        lambda deployable_details: deployable_details.has_storage,
    )

    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            assert "helm.sh/resource-policy" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["helm.sh/resource-policy"] == "delete"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_pvcs_created_if_existing_claims_specified(values, make_templates):
    iterate_deployables_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Storage, {"existingClaim": "something"}
        ),
        lambda deployable_details: deployable_details.has_storage,
    )

    for template in await make_templates(values):
        assert template["kind"] != "PersistentVolumeClaim", (
            f"{template_id(template)} was created despite referencing existingClaims for all PVCs"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_size_passed_through_to_created_pvcs(values, make_templates):
    counter = 1

    def set_pvc_size(deployable_details: DeployableDetails):
        nonlocal counter
        deployable_details.set_helm_values(values, PropertyType.Storage, {"size": f"{counter}Gi"})
        counter += 1

    iterate_deployables_parts(set_pvc_size, lambda deployable_details: deployable_details.has_storage)

    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            deployable_details = template_to_deployable_details(template)
            pvc_requests = template["spec"]["resources"]["requests"]
            assert "storage" in pvc_requests, f"{template_id(template)} didn't specify any storage requests"

            expected_size = deployable_details.get_helm_values(values, PropertyType.Storage)["size"]
            assert expected_size == pvc_requests["storage"], (
                f"{template_id(template)} didn't respect the configured PVC size"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_storageClassName_by_default(values, make_templates):
    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            assert "storageClassName" not in template["spec"], (
                f"{template_id(template)} set spec.storageClassName when it shouldn't"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_storageClassName_passed_through_to_created_pvcs(values, make_templates):
    values.setdefault("storage", {})["storageClassName"] = "global-" + "".join(
        random.choices(string.ascii_lowercase, k=10)
    )
    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            assert "storageClassName" in template["spec"], (
                f"{template_id(template)} did not set spec.storageClassName despite being configured to"
            )
            assert values["storage"]["storageClassName"] == template["spec"]["storageClassName"], (
                f"{template_id(template)} didn't respect the configured global storageClassName"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_individual_storageClassName_passed_through_to_created_pvcs(values, make_templates):
    values.setdefault("storage", {})["storageClassName"] = "global-" + "".join(
        random.choices(string.ascii_lowercase, k=10)
    )
    iterate_deployables_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Storage, {"storageClassName": "".join(random.choices(string.ascii_lowercase, k=10))}
        ),
        lambda deployable_details: deployable_details.has_storage,
    )

    for template in await make_templates(values):
        if template["kind"] == "PersistentVolumeClaim":
            assert "storageClassName" in template["spec"], (
                f"{template_id(template)} did not set spec.storageClassName despite being configured to"
            )
            deployable_details = template_to_deployable_details(template)

            expected_storageClassName = deployable_details.get_helm_values(values, PropertyType.Storage)[
                "storageClassName"
            ]
            assert expected_storageClassName == template["spec"]["storageClassName"], (
                f"{template_id(template)} didn't respect the configured PVC storageClassName"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvc_has_no_selector_by_default(templates):
    for template in templates:
        if template["kind"] in ["PersistentVolumeClaim"]:
            pvc_spec = template["spec"]
            assert "selectors" not in pvc_spec, (
                f"{template_id(template)} has a default selector when one isn't configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvc_gets_configured_selector(values, make_templates, release_name):
    def set_selector(deployable_details: DeployableDetails):
        selector = {"k8s.element.io/pvc-testing": "".join(random.choices(string.ascii_lowercase))}
        deployable_details.set_helm_values(values, PropertyType.Storage, {"selector": {"matchLabels": selector}})

    iterate_deployables_parts(
        set_selector,
        lambda deployable_details: deployable_details.has_storage,
    )
    for template in await make_templates(values):
        if template["kind"] in ["PersistentVolumeClaim"]:
            pvc_spec = template["spec"]
            assert "selector" in pvc_spec, f"{template_id(template)} doesn't have a selector when one is configured"

            deployable_details = template_to_deployable_details(template)
            expected_selector = deployable_details.get_helm_values(values, PropertyType.Storage)["selector"]
            assert pvc_spec["selector"] == expected_selector, f"{template_id(template)} has an unexpected selector"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvc_has_no_volumeName_by_default(templates):
    for template in templates:
        if template["kind"] in ["PersistentVolumeClaim"]:
            pvc_spec = template["spec"]
            assert "volumeName" not in pvc_spec, (
                f"{template_id(template)} has a default volumeName when one isn't configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvc_gets_configured_volumeName(values, make_templates, release_name):
    def set_volumeName(deployable_details: DeployableDetails):
        volumeName = "".join(random.choices(string.ascii_lowercase))
        deployable_details.set_helm_values(values, PropertyType.Storage, {"volumeName": volumeName})

    iterate_deployables_parts(
        set_volumeName,
        lambda deployable_details: deployable_details.has_storage,
    )
    for template in await make_templates(values):
        if template["kind"] in ["PersistentVolumeClaim"]:
            pvc_spec = template["spec"]
            assert "volumeName" in pvc_spec, f"{template_id(template)} doesn't have a volumeName when one is configured"

            deployable_details = template_to_deployable_details(template)
            expected_volumeName = deployable_details.get_helm_values(values, PropertyType.Storage)["volumeName"]
            assert pvc_spec["volumeName"] == expected_volumeName, (
                f"{template_id(template)} has an unexpected volumeName"
            )
