# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random

import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_no_dnsPolicy_by_default_unless_hostNetwork(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]

        if pod_spec.get("hostNetwork", False):
            assert "dnsPolicy" in pod_spec, (
                f"{pod_template_details.manifest_id} sets hostNetwork=true but doesn't set dnsPolicy"
            )
            assert pod_spec["dnsPolicy"] == "ClusterFirstWithHostNet", (
                f"{pod_template_details.manifest_id} sets hostNetwork=true but doesn't set "
                "dnsPolicy=ClusterFirstWithHostNet"
            )
        else:
            assert "dnsPolicy" not in pod_spec, (
                f"{pod_template_details.manifest_id} does not hostNetwork=true but has set a default dnsPolicy"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_dnsPolicy(values, make_templates):
    def set_dnspolicy(deployable_details: DeployableDetails):
        dnsPolicy = random.choice(["ClusterFirst", "ClusterFirstWithHostNetwork", "Default", "None"])
        deployable_details.set_helm_values(values, PropertyType.DNSPolicy, dnsPolicy)

    iterate_deployables_parts(set_dnspolicy, lambda deployable_details: deployable_details.makes_outbound_requests)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]

        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.makes_outbound_requests:
            assert "dnsPolicy" not in pod_spec, (
                f"{pod_template_details.manifest_id} has set a dnsPolicy but doesn't make outbound requests"
            )
            continue

        assert "dnsPolicy" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a dnsPolicy when one is configured"
        )

        expected_dnsPolicy = deployable_details.get_helm_values(values, PropertyType.DNSPolicy)
        assert pod_spec["dnsPolicy"] == expected_dnsPolicy, (
            f"{pod_template_details.manifest_id} has an unexpected dnsPolicy"
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
async def test_pod_gets_configured_dnsConfig(values, make_templates, release_name):
    counter = 1

    def set_dnsConfig(deployable_details: DeployableDetails):
        nonlocal counter
        dnsConfig = deepfreeze(
            {
                "nameservers": [f"10.0.0.{counter}", "8.8.8.8"],
                "searches": [f"{{{{ $.Release.Name }}}}-suffix-{counter}.example.com"],
                "options": [{"name": "ndots", "value": str(counter)}],
            }
        )
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.DNSConfig, dnsConfig)

    iterate_deployables_parts(set_dnsConfig, lambda deployable_details: deployable_details.makes_outbound_requests)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        deployable_details = pod_template_details.deployable_details()

        if not deployable_details.makes_outbound_requests:
            assert "dnsConfig" not in pod_spec, (
                f"{pod_template_details.manifest_id} has a dnsConfig but doesn't make outbound requests"
            )
            continue

        assert "dnsConfig" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have a dnsConfig when one is configured"
        )

        expected_dnsConfig = deployable_details.get_helm_values(values, PropertyType.DNSConfig)
        expected_dnsConfig = deepfreeze(
            {
                "nameservers": expected_dnsConfig["nameservers"],
                "searches": [
                    search.replace("{{ $.Release.Name }}", release_name) for search in expected_dnsConfig["searches"]
                ],
                "options": expected_dnsConfig["options"],
            }
        )
        assert pod_spec["dnsConfig"] == expected_dnsConfig, (
            f"{pod_template_details.manifest_id} has an unexpected dnsConfig"
        )
