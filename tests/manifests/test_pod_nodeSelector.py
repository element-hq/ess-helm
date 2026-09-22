# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_nodeSelector_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "nodeSelector" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a default nodeSelector when one isn't configured"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_nodeSelector(values, make_templates):
    def set_nodeSelector(deployable_details: DeployableDetails):
        nodeSelector = {"k8s.element.io/testing": "".join(random.choices(string.ascii_lowercase, k=5))}
        deployable_details.set_helm_values(values, PropertyType.NodeSelector, nodeSelector)

    iterate_deployables_workload_parts(set_nodeSelector)

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "nodeSelector" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a nodeSelector when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_nodeSelector = deployable_details.get_helm_values(values, PropertyType.NodeSelector)
        assert pod_spec["nodeSelector"] == expected_nodeSelector, (
            f"{pod_template_details.manifest_id} has an unexpected nodeSelector"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_global_nodeSelector(values, make_templates):
    global_nodeSelector = {"k8s.element.io/testing": "".join(random.choices(string.ascii_lowercase))}
    values["nodeSelector"] = global_nodeSelector

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec["nodeSelector"] == global_nodeSelector, (
            f"{pod_template_details.manifest_id} has an unexpected nodeSelector"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
# Unlike with e.g. tolerations this doesn't merge but overrides
# This is because nodeSelectors are restrictions and AND rather than OR
# Merging would mean that a component needs to find a node that has the labels from both
async def test_component_nodeSelector_overrides_global(values, make_templates):
    global_nodeSelector = {"k8s.element.io/testing": "".join(random.choices(string.ascii_lowercase, k=4))}
    values["nodeSelector"] = global_nodeSelector

    def set_nodeSelector(deployable_details: DeployableDetails):
        nodeSelector = {"k8s.element.io/testing": "".join(random.choices(string.ascii_lowercase, k=5))}
        deployable_details.set_helm_values(values, PropertyType.NodeSelector, nodeSelector)

    iterate_deployables_workload_parts(set_nodeSelector)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        deployable_details = pod_template_details.deployable_details()
        expected_nodeSelector = deployable_details.get_helm_values(values, PropertyType.NodeSelector)
        # These can't be equal by random.choices returning the same value by chance as they have different
        # values for k (how many values to return)
        assert expected_nodeSelector != global_nodeSelector, (
            f"{pod_template_details.manifest_id} incorrectly expects the global nodeSelector"
        )
        assert pod_spec["nodeSelector"] == expected_nodeSelector, (
            f"{pod_template_details.manifest_id} has an unexpected nodeSelector"
        )
