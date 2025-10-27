# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import string

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    template_id,
    template_to_deployable_details,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_nodeSelector_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "nodeSelector" not in pod_spec, (
                f"{template_id(template)} has a default nodeSelector when one isn't configured"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_nodeSelector(values, make_templates, release_name):
    def set_nodeSelector(deployable_details: DeployableDetails):
        nodeSelector = {"k8s.element.io/testing": "".join(random.choices(string.ascii_lowercase))}
        deployable_details.set_helm_values(values, PropertyType.NodeSelector, nodeSelector)

    iterate_deployables_workload_parts(set_nodeSelector)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            assert "nodeSelector" in pod_spec, (
                f"{template_id(template)} doesn't have a nodeSelector when one is configured"
            )

            deployable_details = template_to_deployable_details(template)
            expected_nodeSelector = deployable_details.get_helm_values(values, PropertyType.NodeSelector)
            assert pod_spec["nodeSelector"] == expected_nodeSelector, (
                f"{template_id(template)} has an unexpected nodeSelector"
            )
