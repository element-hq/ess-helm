# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections import defaultdict

import pytest

from . import DeployableDetails, PropertyType, all_deployables_details, values_files_to_test
from .utils import iterate_deployables_workload_parts, template_id, template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sets_extra_env(values, make_templates):
    extra_envs = [
        {"name": "a_string", "value": "first"},
        {"name": "a_string", "value": "second"},
        {"name": "b_boolean", "value": str(True)},
        {"name": "c_integer", "value": str(1)},
        {"name": "d_float", "value": str(1.1)},
    ]

    def set_extra_env(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Env, extra_envs)

    iterate_deployables_workload_parts(set_extra_env)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            pod_spec = template["spec"]["template"]["spec"]
            for container in pod_spec.get("initContainers", []) + pod_spec["containers"]:
                env_keys = [env["name"] for env in container.get("env", [])]
                assert len(env_keys) == len(set(env_keys)), (
                    f"{template_id(template)} has container {container['name']} "
                    f"with env keys are not unique: {env_keys}"
                )

                for env in container.get("env", []):
                    if "valueFrom" in env:
                        continue
                    assert type(env["value"]) is str, (
                        f"{template_id(template)} has container {container['name']} "
                        f"which has an non-string value: {env}"
                    )

                command = " ".join(container.get("command", []))
                # We only provide extraEnv to specific matrix-tools init containers
                if command.startswith("/matrix-tools") and container["command"][1] not in ["render-config", "syn2mas"]:
                    continue
                if container["name"] in ["copy-mas-cli", "syn2mas-check"]:
                    continue

                for key in [extra_env["name"] for extra_env in extra_envs]:
                    assert key in env_keys, (
                        f"{template_id(template)} has container {container['name']} "
                        "that is missing some of the extra env that's being injected"
                    )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_built_in_env_cant_be_overwritten(values, make_templates):
    built_in_env = defaultdict(lambda: defaultdict(None))

    # Unset any env in the values file under test as this env can be overridden
    for deployable_details in all_deployables_details:
        if deployable_details.has_workloads:
            deployable_details.get_helm_values(values, PropertyType.Env, default_value=[]).clear()

    # Collect the env set for each and every container
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            pod_spec = template["spec"]["template"]["spec"]
            for container in pod_spec.get("initContainers", []) + pod_spec["containers"]:
                deployable_details = template_to_deployable_details(template, container["name"])
                built_in_env[deployable_details][container["name"]] = [env["name"] for env in container.get("env", [])]

    def override_env(deployable_details: DeployableDetails):
        # For all env vars used across all containers for this deployable details attempt to overwrite the value
        user_env = []
        for container_name in built_in_env[deployable_details]:
            for env_key in built_in_env[deployable_details][container_name]:
                user_env.append({"name": env_key, "value": "from-user"})
        deployable_details.set_helm_values(values, PropertyType.Env, user_env)

    iterate_deployables_workload_parts(override_env)

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            pod_spec = template["spec"]["template"]["spec"]
            for container in pod_spec.get("initContainers", []) + pod_spec["containers"]:
                deployable_details = template_to_deployable_details(template, container["name"])

                env_keys_from_chart = built_in_env[deployable_details][container["name"]]
                for env_var in container.get("env", []):
                    # We can't just look for the value being 'from-user' as a deployable_details may have multiple
                    # containers each setting different env vars. We'll have provided a 'from-user' env var override
                    # for all of those env vars and so 'from-user' will legitimately be present on some containers
                    if env_var["name"] in env_keys_from_chart:
                        if "valueFrom" in env_var:
                            continue
                        assert env_var["value"] != "from-user", (
                            f"{template_id(template)}/{container['name']} allowed env var "
                            f"{env_var['name']} to be overwritten"
                        )
