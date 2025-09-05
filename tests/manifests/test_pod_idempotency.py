# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml

from . import values_files_to_test
from .utils import helm_template, template_id


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
        (await _patch_version_chart()), release_name, namespace, values, has_service_monitor_crd=True, skip_cache=True
    ):
        first_render[template_id(template)] = template
    for template in await helm_template(
        (await _patch_version_chart()), release_name, namespace, values, has_service_monitor_crd=True, skip_cache=True
    ):
        second_render[template_id(template)] = template

    assert set(first_render.keys()) == set(second_render.keys()), "Values file should render the same templates"
    for id in first_render:
        assert first_render[id] != second_render[id], (
            f"Error with {template_id(first_render[id])} : "
            "Templates should be different because the version changed, causing the chart version label to change"
        )
        first_render[id]["metadata"]["labels"].pop("helm.sh/chart")
        second_render[id]["metadata"]["labels"].pop("helm.sh/chart")

        # This will always vary even when we have a sidecar process to send a reload signal to HAProxy
        if id == f"ConfigMap/{release_name}-synapse-haproxy":
            first_render[id]["data"].pop("ess-version.json")
            second_render[id]["data"].pop("ess-version.json")
        # We can either remove this label as a whole or remove `ess-version.json` for the calculation for this label
        # when we have a sidecar process to send a reload signal to HAProxy. If we have that sidecar process the
        # rationale for the hash label disappears.
        # The HAProxy doesn't neccessarily have the label either if it is only being deployed for the well-knowns
        elif (
            id == f"Deployment/{release_name}-haproxy"
            and "k8s.element.io/synapse-haproxy-config-hash" in first_render[id]["metadata"]["labels"]
        ):
            first_render[id]["metadata"]["labels"].pop("k8s.element.io/synapse-haproxy-config-hash")
            second_render[id]["metadata"]["labels"].pop("k8s.element.io/synapse-haproxy-config-hash")
            first_render[id]["spec"]["template"]["metadata"]["labels"].pop("k8s.element.io/synapse-haproxy-config-hash")
            second_render[id]["spec"]["template"]["metadata"]["labels"].pop(
                "k8s.element.io/synapse-haproxy-config-hash"
            )

        assert first_render[id] == second_render[id], (
            f"Error with {template_id(first_render[id])} : "
            "Templates should be the same after removing the chart version label as it should be the only difference"
        )
