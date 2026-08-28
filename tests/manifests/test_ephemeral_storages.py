# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, iterate_pod_template


def _assert_empty_dir_volumes(
    pod_template_details, deployable_details: DeployableDetails, values: dict[str, Any], base_values: dict[str, Any]
):
    rendered_config_size_limit = values.get("matrixTools", base_values["matrixTools"])["ephemeralStorages"][
        "renderedConfig"
    ]["sizeLimit"]
    volumes = pod_template_details.pod_template["spec"].get("volumes", [])
    expected_ephemeral_storages = deployable_details.get_helm_values(values, PropertyType.EphemeralStorages)

    for volume in volumes:
        if "emptyDir" not in volume:
            continue
        volume_name = volume["name"]

        assert deployable_details.has_ephemeral_storage, (
            f"{pod_template_details.manifest_id}: found an emptyDir volume '{volume_name}' but deployable is not "
            "defined with ephemeral storage"
        )
        if volume_name == "rendered-config":
            actual = volume["emptyDir"].get("sizeLimit")
            assert rendered_config_size_limit == actual, (
                f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' "
                f"sizeLimit is {actual!r} but expected {rendered_config_size_limit!r}"
            )
        else:
            assert volume_name in deployable_details.ephemeral_storages, (
                f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' "
                f"is not registered in {deployable_details.name}'s ephemeral_storage"
            )
            assert expected_ephemeral_storages, (
                f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' but no ephemeralVolume is defined"
            )
            expected_ephemeral_volume = expected_ephemeral_storages[deployable_details.ephemeral_storages[volume_name]][
                "sizeLimit"
            ]
            actual = volume["emptyDir"].get("sizeLimit")
            assert expected_ephemeral_volume == actual, (
                f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' "
                f"sizeLimit is {actual!r} but expected {expected_ephemeral_volume!r}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ephemeral_storage_defaults(templates, values, base_values):
    """Every shipped default sizeLimit flows through to the rendered manifest."""

    for pod_template_details in iterate_pod_template(templates):
        volumes = pod_template_details.pod_template["spec"].get("volumes", [])
        assert (
            any("emptyDir" in v for v in volumes) == pod_template_details.deployable_details().has_ephemeral_storage
        ), f"{pod_template_details.manifest_id}: emptyDir volumes is not consistent with has_ephemeral_storage"
        for volume in volumes:
            if "emptyDir" not in volume:
                continue
            volume_name = volume["name"]
            assert volume["emptyDir"].get("sizeLimit"), (
                f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' is lacking sizeLimit"
            )
            assert "medium" in volume["emptyDir"], (
                f"{pod_template_details.manifest_id} has emptyDir {volume['name']} but doesn't set the medium"
            )
            assert volume["emptyDir"]["medium"] == "Memory", (
                f"{pod_template_details.manifest_id} has emptyDir {volume['name']} that isn't Memory backed"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ephemeral_storage_passed_through(values, base_values, make_templates):
    """Each sizeLimit is independently configurable and flows through to the manifest.

    A distinct sentinel is assigned per unique values path so that a mis-wired
    template (e.g. rendering the wrong component's value) fails the assertion,
    while correctly-shared volumes (e.g. rendered-config) still match.
    """
    counter = 0
    values.setdefault("matrixTools", {}).setdefault("ephemeralStorages", {}).setdefault("renderedConfig", {})[
        "sizeLimit"
    ] = f"{counter}Mi"

    def set_ephemeral_storage_empty_dir_size_limit(deployable_details: DeployableDetails):
        nonlocal counter
        ephemeral_storages = {}
        for ephemeral_volume in deployable_details.ephemeral_storages.values():
            counter += 1
            ephemeral_storages[ephemeral_volume] = {"sizeLimit": f"{counter}Mi"}
        if ephemeral_storages:
            deployable_details.set_helm_values(values, PropertyType.EphemeralStorages, ephemeral_storages)

    iterate_deployables_parts(
        set_ephemeral_storage_empty_dir_size_limit, lambda deployable_details: deployable_details.has_ephemeral_storage
    )

    templates = await make_templates(values)
    for pod_template_details in iterate_pod_template(templates):
        deployable_details = pod_template_details.deployable_details()
        _assert_empty_dir_volumes(pod_template_details, deployable_details, values, base_values)
