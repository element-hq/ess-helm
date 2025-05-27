# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, workloads_values_files_to_test
from .utils import iterate_deployables_workload_parts, template_id

extra_env = {"a_string": "a", "b_boolean": True, "c_integer": 1, "d_float": 1.1}


@pytest.mark.parametrize("values_file", workloads_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_unique_env_name_in_containers(values, make_templates):
    def set_extra_env(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values, PropertyType.Env, [{"name": k, "value": str(v)} for k, v in extra_env.items()]
        )

    iterate_deployables_workload_parts(set_extra_env)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            for container in template["spec"]["template"]["spec"]["containers"]:
                env_keys = [env["name"] for env in container.get("env", [])]
                assert len(env_keys) == len(set(env_keys)), (
                    f"{template_id(template)} has container {container['name']} "
                    "with env keys are not unique: {env_keys}"
                )
                for key in extra_env:
                    assert key in env_keys, (
                        f"{template_id(template)} has container {container['name']} "
                        "that is missing some of the extra env that's being injected"
                    )


@pytest.mark.parametrize("values_file", workloads_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_env_values_are_strings_in_containers(values, make_templates):
    def set_extra_env(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values, PropertyType.Env, [{"name": k, "value": str(v)} for k, v in extra_env.items()]
        )

    iterate_deployables_workload_parts(set_extra_env)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            for container in template["spec"]["template"]["spec"]["containers"]:
                for env in container.get("env", []):
                    assert type(env["value"]) is str, (
                        f"{template_id(template)} has container {container['name']} "
                        "which has an non-string value: {env}"
                    )
