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
async def test_pod_has_no_dnsConfig_by_default(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "dnsConfig" not in pod_spec, (
            f"{pod_template_details.manifest_id} has a dnsConfig when one isn't configured"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_dnsConfig(values, make_templates):
    dns_config = {
        "nameservers": ["1.1.1.1", "8.8.8.8"],
        "searches": ["my.dns.search.suffix"],
        "options": [{"name": "ndots", "value": "2"}],
    }

    def set_dnsConfig(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.DnsConfig, dns_config)

    iterate_deployables_parts(set_dnspolicy, lambda deployable_details: deployable_details.makes_outbound_requests)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "dnsConfig" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a dnsConfig when one is configured"
        )

        deployable_details = pod_template_details.deployable_details()
        expected_dnsConfig = deployable_details.get_helm_values(values, PropertyType.DnsConfig)
        assert pod_spec["dnsConfig"] == expected_dnsConfig, (
            f"{pod_template_details.manifest_id} has an unexpected dnsConfig"
        )