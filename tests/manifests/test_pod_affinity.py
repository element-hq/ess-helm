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


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_affinity_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "affinity" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a default affinity when one isn't configured"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_affinity(values, make_templates):
    # All 3 affinity types are configured at once: they don't interfere with each other, so a
    # single render checks them all for every deployable.
    def set_affinity(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Affinity, _all_affinity_types())

    iterate_deployables_workload_parts(set_affinity)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "affinity" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have an affinity when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_affinity = deployable_details.get_helm_values(values, PropertyType.Affinity)
        assert pod_spec["affinity"] == deepfreeze(expected_affinity), (
            f"{pod_template_details.manifest_id} has an unexpected affinity"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_affinity_renders(values, make_templates):
    global_affinity = _all_affinity_types()
    values["affinity"] = global_affinity

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec.get("affinity") == deepfreeze(global_affinity), (
            f"{pod_template_details.manifest_id} doesn't inherit the global affinity"
        )


@pytest.mark.parametrize("overridden_type", AFFINITY_TYPES)
@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_component_affinity_types_are_resolved_independently(overridden_type, values, make_templates):
    # Global sets all 3 affinity types. Each render gives every component a fragment where each
    # affinity type has a different treatment: one type is overridden, the next one is blanked
    # out with {} and the last one is left out, so it stays inherited from the global affinity.
    # The treatments rotate with the parametrization: across the 3 renders every type gets
    # every treatment for every component, in half the renders these behaviors used to need.
    type_index = AFFINITY_TYPES.index(overridden_type)
    blanked_type = AFFINITY_TYPES[(type_index + 1) % len(AFFINITY_TYPES)]
    inherited_type = AFFINITY_TYPES[(type_index + 2) % len(AFFINITY_TYPES)]

    global_affinity = _all_affinity_types()
    values["affinity"] = global_affinity

    component_affinity = _affinity_for(overridden_type) | {blanked_type: {}}

    def set_affinity(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Affinity, component_affinity)

    iterate_deployables_workload_parts(set_affinity)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        affinity = pod_template_details.pod_template["spec"].get("affinity", {})
        assert affinity.get(overridden_type) == deepfreeze(component_affinity[overridden_type]), (
            f"{pod_template_details.manifest_id} did not override the global {overridden_type} with the component one"
        )
        assert blanked_type not in affinity, (
            f"{pod_template_details.manifest_id} did not blank out the global {blanked_type}"
        )
        assert affinity.get(inherited_type) == deepfreeze(global_affinity[inherited_type]), (
            f"{pod_template_details.manifest_id} dropped the global {inherited_type}"
        )
