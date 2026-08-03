# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_default_dnsPolicy(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "dnsPolicy" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a dnsPolicy"
        )
        assert pod_spec["dnsPolicy"] == "ClusterFirst", (
            f"{pod_template_details.manifest_id} doesn't have the expected default dnsPolicy"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_dnsPolicy(values, make_templates):
    def set_dnsPolicy(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.DnsPolicy, "None")

    iterate_deployables_workload_parts(set_dnsPolicy)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert pod_spec.get("dnsPolicy") == "None", (
            f"{pod_template_details.manifest_id} doesn't have the configured dnsPolicy"
        )