# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import copy

import pytest

from . import DeployableDetails, PropertyType, all_deployables_details, values_files_to_test
from .utils import iterate_deployables_workload_parts


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_dont_automount_serviceaccount_tokens(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            id = f"{template['kind']}/{template['metadata']['name']}"

            assert not template["spec"]["template"]["spec"]["automountServiceAccountToken"], (
                f"ServiceAccount token automounted for {id}"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_serviceaccount_named_as_per_pod_controller_by_default(templates):
    workloads_by_id = {}
    serviceaccount_names = set()
    covered_serviceaccount_names = set()
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            workloads_by_id[f"{template['kind']}/{template['metadata']['name']}"] = template
        elif template["kind"] == "ServiceAccount":
            serviceaccount_names.add(template["metadata"]["name"])

    for id, template in workloads_by_id.items():
        assert "serviceAccountName" in template["spec"]["template"]["spec"], (
            f"{id} does not set an explicit ServiceAccount"
        )

        serviceaccount_name = template["spec"]["template"]["spec"]["serviceAccountName"]
        covered_serviceaccount_names.add(serviceaccount_name)

        assert serviceaccount_name in serviceaccount_names, f"{id} does not reference a created ServiceAccount"

        # All Synapse workers use the same ServiceAccount. k8s.element.io/synapse-instance is a common label
        # that doesn't have the process type suffixed, so use that
        if "k8s.element.io/synapse-instance" in template["metadata"]["labels"]:
            expected_serviceaccount_name = template["metadata"]["labels"]["k8s.element.io/synapse-instance"]
        else:
            expected_serviceaccount_name = template["metadata"]["name"]
        assert expected_serviceaccount_name == serviceaccount_name, f"{id} uses unexpected ServiceAccount"

    assert serviceaccount_names == covered_serviceaccount_names, f"{id} created ServiceAccounts that it shouldn't have"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_uses_serviceaccount_named_as_values_if_specified(values, make_templates):
    def service_account_name(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values, PropertyType.ServiceAccount, {"name": f"{deployable_details.name}-pytest"}
        )
        deployable_details.set_helm_values(
            values, PropertyType.Labels, {"expected.name": f"{deployable_details.name}-pytest"}
        )

    iterate_deployables_workload_parts(service_account_name)

    workloads_by_id = {}
    serviceaccount_names = []
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            workloads_by_id[f"{template['kind']}/{template['metadata']['name']}"] = template
        elif template["kind"] == "ServiceAccount":
            serviceaccount_names.append(template["metadata"]["name"])

    for id, template in workloads_by_id.items():
        assert "serviceAccountName" in template["spec"]["template"]["spec"], (
            f"{id} does not set an explicit ServiceAccount"
        )
        assert template["spec"]["template"]["spec"]["serviceAccountName"] in serviceaccount_names, (
            f"{id} does not reference a created ServiceAccount"
        )
        assert (
            template["metadata"]["labels"]["expected.name"]
            == template["spec"]["template"]["spec"]["serviceAccountName"]
        ), f"{id} uses unexpected ServiceAccount"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_does_not_create_serviceaccounts_if_configured_not_to(values, make_templates):
    for deployable_details in all_deployables_details:
        if not deployable_details.has_workloads:
            continue

        values_to_modify = copy.deepcopy(values)
        deployable_details.set_helm_values(values_to_modify, PropertyType.ServiceAccount, {"create": False})
        deployable_details.set_helm_values(values_to_modify, PropertyType.Labels, {"serviceAccount": "none"})

        workloads_by_id = {}
        serviceaccount_names = set()
        covered_serviceaccount_names = set()
        for template in await make_templates(values_to_modify):
            if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
                id_suffix = f" (for {deployable_details.name})"
                workloads_by_id[f"{template['kind']}/{template['metadata']['name']}{id_suffix}"] = template
            elif template["kind"] == "ServiceAccount":
                serviceaccount_names.add(template["metadata"]["name"])

        for id, template in workloads_by_id.items():
            assert "serviceAccountName" in template["spec"]["template"]["spec"], (
                f"{id} does not set an explicit ServiceAccount"
            )

            serviceaccount_name = template["spec"]["template"]["spec"]["serviceAccountName"]
            if template["metadata"]["labels"].get("serviceAccount", "some") == "none":
                assert serviceaccount_name not in serviceaccount_names, (
                    f"{id} specified an existing ServiceAccount: {serviceaccount_name}"
                )
            else:
                covered_serviceaccount_names.add(serviceaccount_name)

        assert serviceaccount_names == covered_serviceaccount_names, (
            f"{id} created ServiceAccounts that it shouldn't have"
        )
