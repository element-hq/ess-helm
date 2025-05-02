# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts

extra_env = {"a_string": "a", "b_boolean": True, "c_integer": 1, "d_float": 1.1}


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_unique_env_name_in_containers(
    deployables_details, values, make_templates, template_to_deployable_details
):
    def set_extra_env(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values, PropertyType.Env, [{"name": k, "value": str(v)} for k, v in extra_env.items()]
        )

    iterate_deployables_parts(
        deployables_details, set_extra_env, lambda deployable_details: deployable_details.has_extra_env
    )

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            id = f"{template['kind']}/{template['metadata']['name']}"
            for container in template["spec"]["template"]["spec"]["containers"]:
                env_keys = [env["name"] for env in container.get("env", [])]
                assert len(env_keys) == len(set(env_keys)), f"Env keys are not unique: {id}, {env_keys}"
                if template_to_deployable_details(template).has_extra_env:
                    for key in extra_env:
                        assert key in env_keys


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_env_values_are_strings_in_containers(deployables_details, values, make_templates):
    def set_extra_env(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(
            values, PropertyType.Env, [{"name": k, "value": str(v)} for k, v in extra_env.items()]
        )

    iterate_deployables_parts(
        deployables_details, set_extra_env, lambda deployable_details: deployable_details.has_extra_env
    )

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            id = f"{template['kind']}/{template['metadata']['name']}"
            for container in template["spec"]["template"]["spec"]["containers"]:
                for env in container.get("env", []):
                    assert type(env["value"]) is str, (
                        f"{id} has container {container['name']} which has an non-string value: {env}"
                    )
