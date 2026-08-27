# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import copy
from typing import Any

import pytest

from . import DeployableDetails, all_deployables_details, values_files_to_test
from .utils import iterate_pod_template


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _set_value_at_path(values: dict[str, Any], write_path: tuple[str, ...], value: Any) -> None:
    fragment = values
    for key in write_path[:-1]:
        fragment = fragment.setdefault(key, {})
    fragment[write_path[-1]] = value


def _assert_empty_dir_volumes(pod_template_details, deployable_details: DeployableDetails, values: dict[str, Any]):
    volumes = pod_template_details.pod_template["spec"].get("volumes", [])
    for volume in volumes:
        if "emptyDir" not in volume:
            continue
        volume_name = volume["name"]
        assert volume_name in deployable_details.ephemeral_storage, (
            f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' "
            f"is not registered in {deployable_details.name}'s ephemeral_storage"
        )
        expected = deployable_details.get_ephemeral_storage_size_limit(volume_name, values)
        actual = volume["emptyDir"].get("sizeLimit")
        assert expected == actual, (
            f"{pod_template_details.manifest_id}: emptyDir volume '{volume_name}' "
            f"sizeLimit is {actual!r} but expected {expected!r}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ephemeral_storage_defaults(templates, values, base_values):
    """Every shipped default sizeLimit flows through to the rendered manifest."""
    effective_values = _deep_merge(base_values, values)
    for pod_template_details in iterate_pod_template(templates):
        deployable_details = pod_template_details.deployable_details()
        _assert_empty_dir_volumes(pod_template_details, deployable_details, effective_values)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_ephemeral_storage_passed_through(values, make_templates):
    """Each sizeLimit is independently configurable and flows through to the manifest.

    A distinct sentinel is assigned per unique values path so that a mis-wired
    template (e.g. rendering the wrong component's value) fails the assertion,
    while correctly-shared volumes (e.g. rendered-config) still match.
    """
    counter = 0
    path_to_sentinel: dict[tuple[str, ...], str] = {}
    for deployable_details in all_deployables_details:
        for ephemeral_volume in deployable_details.ephemeral_storage.values():
            write_path = ephemeral_volume.values_file_path.write_path
            if write_path is None:
                continue
            if write_path not in path_to_sentinel:
                counter += 1
                path_to_sentinel[write_path] = f"{counter}Mi"
            _set_value_at_path(values, write_path, path_to_sentinel[write_path])

    templates = await make_templates(values)
    for pod_template_details in iterate_pod_template(templates):
        deployable_details = pod_template_details.deployable_details()
        _assert_empty_dir_volumes(pod_template_details, deployable_details, values)
