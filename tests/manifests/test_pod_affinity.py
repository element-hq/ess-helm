# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)

AFFINITY_TYPES = ["nodeAffinity", "podAffinity", "podAntiAffinity"]


def _random_value():
    return "".join(random.choices(string.ascii_lowercase, k=8))


def _affinity_for(affinity_type: str, value: str | None = None) -> dict:
    """Builds a single-type, schema-valid affinity fragment, e.g. {"nodeAffinity": {...}}."""
    value = value or _random_value()
    if affinity_type == "nodeAffinity":
        return {
            "nodeAffinity": {
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": [
                        {
                            "matchExpressions": [
                                {
                                    "key": "k8s.element.io/testing",
                                    "operator": "In",
                                    "values": [value],
                                }
                            ]
                        }
                    ]
                }
            }
        }
    if affinity_type in ("podAffinity", "podAntiAffinity"):
        return {
            affinity_type: {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "weight": 100,
                        "podAffinityTerm": {
                            "labelSelector": {"matchLabels": {"k8s.element.io/testing": value}},
                            "topologyKey": "kubernetes.io/hostname",
                        },
                    }
                ]
            }
        }
    raise ValueError(f"Unknown affinity type {affinity_type}")


def _all_affinity_types() -> dict:
    """A fragment setting all 3 affinity types, each with a distinct random value."""
    affinity = {}
    for affinity_type in AFFINITY_TYPES:
        affinity.update(_affinity_for(affinity_type))
    return affinity


def _expected_affinity(global_affinity: dict, component_affinity: dict | None) -> dict:
    """
    Mirrors the per-type resolution the chart applies: for each affinity type a component that
    sets it overrides only that type (an empty value blanks it out); otherwise it is inherited
    from the global affinity.
    """
    component_affinity = component_affinity or {}
    expected = {}
    for affinity_type in AFFINITY_TYPES:
        if affinity_type in component_affinity:
            if component_affinity[affinity_type]:
                expected[affinity_type] = component_affinity[affinity_type]
        elif global_affinity.get(affinity_type):
            expected[affinity_type] = global_affinity[affinity_type]
    return expected


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_affinity_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "affinity" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a default affinity when one isn't configured"
        )


@pytest.mark.parametrize("affinity_type", AFFINITY_TYPES)
@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_affinity(affinity_type, values, make_templates, release_name):
    def set_affinity(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Affinity, _affinity_for(affinity_type))

    iterate_deployables_workload_parts(set_affinity)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "affinity" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have an affinity when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_affinity = deployable_details.get_helm_values(values, PropertyType.Affinity)
        assert pod_spec["affinity"] == deepfreeze(expected_affinity), (
            f"{pod_template_details.manifest_id} has an unexpected {affinity_type}"
        )


@pytest.mark.parametrize("affinity_type", AFFINITY_TYPES)
@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_affinity_renders(affinity_type, values, make_templates):
    global_affinity = _affinity_for(affinity_type)
    values["affinity"] = global_affinity

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec.get("affinity") == deepfreeze(global_affinity), (
            f"{pod_template_details.manifest_id} doesn't inherit the global {affinity_type}"
        )


@pytest.mark.parametrize("affinity_type", AFFINITY_TYPES)
@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_override_is_isolated_to_its_type(affinity_type, values, make_templates):
    # Global sets all 3 affinity types; a component overrides only one of them.
    global_affinity = _all_affinity_types()
    values["affinity"] = global_affinity

    component_override = _affinity_for(affinity_type)

    def set_affinity(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Affinity, component_override)

    iterate_deployables_workload_parts(set_affinity)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        deployable_details = pod_template_details.deployable_details()
        component_affinity = deployable_details.get_helm_values(values, PropertyType.Affinity)
        expected_affinity = _expected_affinity(global_affinity, component_affinity)
        assert pod_spec.get("affinity") == deepfreeze(expected_affinity), (
            f"{pod_template_details.manifest_id} did not isolate the {affinity_type} override to that type"
        )
        # The other affinity types must still come from the global affinity.
        for other_type in AFFINITY_TYPES:
            if other_type == affinity_type:
                continue
            if component_affinity and other_type in component_affinity:
                continue
            assert pod_spec["affinity"].get(other_type) == deepfreeze(global_affinity[other_type]), (
                f"{pod_template_details.manifest_id} dropped the global {other_type} when overriding {affinity_type}"
            )


@pytest.mark.parametrize("affinity_type", AFFINITY_TYPES)
@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_can_blank_global_affinity_type(affinity_type, values, make_templates):
    # Global sets all 3 affinity types; a component blanks out just one of them with {}.
    global_affinity = _all_affinity_types()
    values["affinity"] = global_affinity

    def blank_affinity(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Affinity, {affinity_type: {}})

    iterate_deployables_workload_parts(blank_affinity)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        affinity = pod_spec.get("affinity", {})
        assert affinity_type not in affinity, (
            f"{pod_template_details.manifest_id} did not blank out the global {affinity_type}"
        )
        # The non-blanked affinity types must still be inherited from the global affinity.
        for other_type in AFFINITY_TYPES:
            if other_type == affinity_type:
                continue
            assert affinity.get(other_type) == deepfreeze(global_affinity[other_type]), (
                f"{pod_template_details.manifest_id} dropped the global {other_type} when blanking {affinity_type}"
            )
