# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_parts,
    template_id,
    template_to_deployable_details,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_has_hostAliases_if_appropriate(values, make_templates, release_name):
    counter = 1

    def set_hostAliases(deployable_details: DeployableDetails):
        nonlocal counter
        hostAliases = (
            deepfreeze(
                {"ip": f"192.0.2.{counter}", "hostnames": ["a-{{ $.Release.Name }}.example.com", "b.example.com"]}
            ),
        )
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.HostAliases, hostAliases)

    iterate_deployables_parts(set_hostAliases, lambda deployable_details: deployable_details.makes_outbound_requests)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            pod_spec = template["spec"]["template"]["spec"]
            deployable_details = template_to_deployable_details(template)

            if not deployable_details.makes_outbound_requests:
                assert "hostAliases" not in pod_spec, (
                    f"{template_id(template)} set hostAliases in its Pod when it doesn't need to"
                )
                continue

            assert "hostAliases" in pod_spec, f"{template_id(template)} doesn't set hostAliases in its Pod"

            expected_hostAliases = deployable_details.get_helm_values(values, PropertyType.HostAliases)
            expected_hostAliases = tuple(
                [
                    deepfreeze(
                        {
                            "ip": alias["ip"],
                            "hostnames": [
                                hostname.replace("{{ $.Release.Name }}", release_name)
                                for hostname in alias["hostnames"]
                            ],
                        }
                    )
                    for alias in expected_hostAliases
                ]
            )
            assert pod_spec["hostAliases"] == expected_hostAliases, (
                f"{template_id(template)} doesn't have the expected hostAliases"
            )
