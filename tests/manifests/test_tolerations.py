# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from frozendict import frozendict

from . import PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, iterate_pod_template

specific_toleration = frozendict(
    {
        "key": "component",
        "operator": "Equals",
        "value": "pytest",
        "effect": "NoSchedule",
    }
)

global_toleration = frozendict(
    {
        "key": "global",
        "operator": "Equals",
        "value": "pytest",
        "effect": "NoSchedule",
    }
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_tolerations_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        assert "tolerations" not in pod_template_details.pod_template["spec"], (
            f"Tolerations unexpectedly present for {pod_template_details.manifest_id}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_components_and_sub_components_render_tolerations(values, make_templates):
    iterate_deployables_workload_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Tolerations, [specific_toleration]
        ),
    )

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        id = pod_template_details.manifest_id

        pod_spec = pod_template_details.pod_template["spec"]
        assert "tolerations" in pod_spec, f"No tolerations for {id}"
        assert len(pod_spec["tolerations"]) == 1, f"Wrong number of tolerations for {id}"
        assert pod_spec["tolerations"][0] == specific_toleration, f"Toleration isn't as expected for {id}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_tolerations_render(values, make_templates):
    values.setdefault("tolerations", []).append(global_toleration)

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        id = pod_template_details.manifest_id

        pod_spec = pod_template_details.pod_template["spec"]
        assert "tolerations" in pod_spec, f"No tolerations for {id}"
        assert len(pod_spec["tolerations"]) == 1, f"Wrong number of tolerations for {id}"
        assert pod_spec["tolerations"][0] == global_toleration, f"Toleration isn't as expected for {id}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_merges_global_and_specific_tolerations(values, make_templates):
    iterate_deployables_workload_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Tolerations, [specific_toleration]
        ),
    )

    # Add twice for uniqueness check. There's no 'overwriting' as if it isn't the same toleration, it gets kept
    values.setdefault("tolerations", []).append(global_toleration)
    values.get("tolerations").append(global_toleration)

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        id = pod_template_details.manifest_id

        pod_spec = pod_template_details.pod_template["spec"]
        assert "tolerations" in pod_spec, f"No tolerations for {id}"
        assert len(pod_spec["tolerations"]) == 2, f"Wrong number of tolerations for {id}"
        assert pod_spec["tolerations"] == (
            specific_toleration,
            global_toleration,
        ), f"Tolerations aren't as expected for {id}"
