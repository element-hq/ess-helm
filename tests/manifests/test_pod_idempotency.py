# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml

from . import values_files_to_test
from .utils import helm_template, template_id


def assert_manifest_are_idempotent(id, release_name, first_manifest, second_manifest, path=tuple()):
    for k, v in first_manifest.items():
        k_path = path + [k]
        if isinstance(v, dict):
            assert v.keys() == second_manifest[k].keys(), (
                f"Error with {id}: {v} != {second_manifest[k]} at path {'.'.join(k_path)}"
            )
            assert_manifest_are_idempotent(id, release_name, v, second_manifest[k], k_path)
        else:
            if k_path == ["metadata", "labels", "helm.sh/chart"]:
                continue
            # This will always vary even when we have a sidecar process to send a reload signal to HAProxy
            if id == f"ConfigMap/{release_name}-synapse-haproxy" and k_path == ["data", "ess-version.json"]:
                continue
            # We can either remove this label as a whole or remove `ess-version.json` for the calculation for this label
            # when we have a sidecar process to send a reload signal to HAProxy. If we have that sidecar process the
            # rationale for the hash label disappears.
            # The HAProxy doesn't neccessarily have the label either if it is only being deployed for the well-knowns
            if (
                id == f"Deployment/{release_name}-haproxy"
                and k_path == ["metadata", "labels", "k8s.element.io/synapse-haproxy-config-hash"]
                or k_path == ["spec", "template", "metadata", "labels", "k8s.element.io/synapse-haproxy-config-hash"]
            ):
                continue
            assert v == second_manifest[k], f"Error with {id}: {v} != {second_manifest[k]} at path {'.'.join(k_path)}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_values_file_renders_idempotent_pods(release_name, namespace, values, helm_client, temp_chart):
    async def _patch_version_chart():
        with open(f"{temp_chart}/Chart.yaml") as f:
            chart = yaml.safe_load(f)
        with open(f"{temp_chart}/Chart.yaml", "w") as f:
            version_parts = chart["version"].split(".")
            minor_version = str(int(version_parts[1]) + 1)
            new_version = ".".join([version_parts[0], minor_version, version_parts[2]])
            chart["version"] = new_version
            yaml.dump(chart, f)
        return await helm_client.get_chart(temp_chart)

    first_render = {}
    second_render = {}
    for template in await helm_template(
        (await _patch_version_chart()),
        release_name,
        namespace,
        values,
        has_cert_manager_crd=True,
        has_service_monitor_crd=True,
        skip_cache=True,
    ):
        first_render[template_id(template)] = template
    for template in await helm_template(
        (await _patch_version_chart()),
        release_name,
        namespace,
        values,
        has_cert_manager_crd=True,
        has_service_monitor_crd=True,
        skip_cache=True,
    ):
        second_render[template_id(template)] = template

    assert set(first_render.keys()) == set(second_render.keys()), "Values file should render the same templates"
    for id in first_render:
        assert first_render[id] != second_render[id], (
            f"Error with {template_id(first_render[id])} : "
            "Templates should be different because the version changed, causing the chart version label to change"
        )
        assert_manifest_are_idempotent(id, release_name, first_render[id], second_render[id], path=[])
