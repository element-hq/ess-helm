# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import re

import pytest

from . import secret_values_files_to_test, values_files_to_test
from .utils import get_or_empty, template_id, template_to_deployable_details


def get_configmap(templates, configmap_name):
    """
    Get the content of a ConfigMap with the given name.
    :param configmap_name: The name of the ConfigMap to retrieve.
    :return: A string containing the content of the ConfigMap, or an empty string if not found.
    """
    for t in templates:
        if t["kind"] == "ConfigMap" and t["metadata"]["name"] == configmap_name:
            return t
    raise ValueError(f"ConfigMap {configmap_name} not found")


def get_secret(templates, other_secrets, secret_name):
    """
    Get the content of a Secret with the given name.
    :param secret_name: The name of the Secret to retrieve.
    :return: A string containing the content of the Secret, or an empty string if not found.
    """
    for t in templates:
        if t["kind"] == "Secret" and t["metadata"]["name"] == secret_name:
            return t
    for s in other_secrets:
        if s["metadata"]["name"] == secret_name:
            return s
    raise ValueError(f"Secret {secret_name} not found")


def get_volume_from_mount(workload_spec, volume_mount):
    """
    Get a specific volume mount from a given template.
    :param template: The template to search within.
    :param volume_name: The name of the volume to retrieve.
    :return: A dictionary representing the volume mount
    """
    # Find the corresponding secret volume that matches the volume mount name
    for v in workload_spec.get("volumes", []):
        if volume_mount["name"] == v["name"]:
            return v
    raise ValueError(
        f"No matching volume found for mount path {volume_mount['mountPath']} in "
        f"[{','.join([v['name'] for v in workload_spec['template']['spec'].get('volumes', [])])}]"
    )


def match_path_in_content(content):
    paths_found = []
    for match_in in content.split("\n"):
        for exclude in ["://", "/bin/sh", "helm.sh/"]:
            if exclude in match_in:
                break
        else:
            # The negative lookahead prevents matching subnets like "192.168.0.0/16", "fe80::/10"
            # And also things that do not start with / like "text/xml"
            # The pattern [^\s\n\")`:%;,/]+[^\s\n\")`:%;,]+ is a regex that will find paths like /path/to/file
            # It expects to find absolute paths only
            # It is possible to add noqa in the content to ignore this path
            for match in re.findall(r"((?<![0-9a-zA-Z:])/[^\s\n\")`:'%;,/]+[^\s\n\")`:'%;,]+(?!.*noqa))", match_in):
                paths_found.append(match)
    return paths_found


def find_paths_in_contents(container, mounted_config_maps, deployable_details):
    paths_found = []
    content_to_match = [e.get("value", "") for e in container.get("env", [])]
    content_to_match += [c for c in container.get("command", [""])[1:] + container.get("args", [])]
    for cm in mounted_config_maps:
        for key, content in cm["data"].items():
            if key not in deployable_details.skip_path_consistency_for_files:
                content_to_match += content.split("\n")

    for content in content_to_match:
        paths_found += match_path_in_content(content)

    return paths_found


def find_mount_paths_and_assert_key_is_consistent(
    container_name, mounted_keys, mount_path, matches_in, deployable_details
):
    found_mount = False
    for match_in in matches_in:
        for match in re.findall(rf"(?:^|\s|\"){mount_path}/([^\s\n\")`;,]+(?!.*noqa))", match_in):
            if f"{mount_path}/{match}" in deployable_details.paths_consistency_noqa:
                continue
            assert f"{mount_path}/{match}" in mounted_keys, (
                f"{mount_path}/{match} used in {container_name} but it is not found "
                f"from any mounted secret or configmap ({deployable_details.name})"
            )
            found_mount = True
    return found_mount


def find_keys_mounts_in_content(mounted_key, matches_in):
    for match_in in matches_in:
        for match in re.findall(rf"(?:^|\s|\"){re.escape(mounted_key)}(?:[^\s\n\")`;,]*)", match_in):
            if match:
                return True
    return False


def get_keys_from_render_config(template):
    keys = []
    for container in template["spec"]["template"]["spec"]["initContainers"]:
        if container["name"].startswith("render-config"):
            args = container.get("args") or container["command"][1:]
            for idx, cmd in enumerate(args):
                if cmd == "-output":
                    keys.append(args[idx + 1].split("/")[-1])
    if keys:
        return keys
    raise AssertionError(
        f"{template_id(template)} has a rendered-config volume, but no render-config output file could be found"
    )


def get_mounts_part(secret_or_cm, volume_mount):
    mounted_keys = []
    if "subPath" in volume_mount:
        mounted_keys.append(volume_mount["mountPath"])
        # The regex tries to find secrets in configfiles, commands & env
        # based on their parent mount point so we drop the filename from
        # the mount path
        mount_parent = "/".join(volume_mount["mountPath"].split("/")[:-1])
    else:
        # When secret data is empty, `data:` is None, so use `get_or_empty`
        for key in get_or_empty(secret_or_cm, "data"):
            # Without subPath, the key will be present as child of the mount path
            mounted_keys.append(f"{volume_mount['mountPath']}/{key}")
        mount_parent = volume_mount["mountPath"]
    return mount_parent, mounted_keys


def filter_mounted_path_only(template, container, mounted_config_maps):
    filtered_configmaps = []
    for configmap in mounted_config_maps:
        filtered_configmap = copy.deepcopy(configmap)
        related_volume_mounts = [
            v
            for v in container["volumeMounts"]
            if get_volume_from_mount(template["spec"], v).get("configMap", {}).get("name", "")
            == configmap["metadata"]["name"]
        ]
        for volume_mount in related_volume_mounts:
            if "subPath" not in volume_mount:
                break  # The whole configmap content is mounted, ignore
        else:
            sub_paths = [v["subPath"] for v in related_volume_mounts]
            # Pop all configmap data keys which are not in a subpath
            for key in configmap["data"]:
                if key not in sub_paths:
                    del filtered_configmap["data"][key]
        filtered_configmaps.append(filtered_configmap)
    return filtered_configmaps


def get_virtual_config_map_from_render_config(template, templates):
    """Build a virtual configmap from the render-config init-container
    so that the test can attempt to discover the configmap content
    in the rendered config files
    """
    for container in template["spec"]["template"]["spec"]["initContainers"]:
        data = {}
        if container["name"].startswith("render-config"):
            paths_to_keys = {}
            for volume_mount in container["volumeMounts"]:
                current_volume = get_volume_from_mount(template["spec"], volume_mount)
                if "configMap" in current_volume:
                    current_config_map = get_configmap(templates, current_volume["configMap"]["name"])
                    if volume_mount.get("subPath"):
                        paths_to_keys[volume_mount["mountPath"] + "/" + volume_mount["subPath"]] = current_config_map[
                            "data"
                        ][volume_mount["subPath"]]
                    else:
                        for key in current_config_map["data"]:
                            paths_to_keys[volume_mount["mountPath"] + "/" + key] = current_config_map["data"][key]
            args = container.get("args") or container["command"][1:]
            source_files = args[3:]
            for p, k in paths_to_keys.items():
                if p in source_files:
                    data[p] = k
        return {"data": data}
    raise RuntimeError("No render-config container found")


def get_keys_from_container_using_rendered_config(template, templates, other_secrets):
    mounted_keys = []
    mounted_keys_to_parents = {}
    for container in template["spec"]["template"]["spec"]["containers"]:
        assert "volumeMounts" in container, f"{container} does not have a 'volumeMounts' field"
        if "rendered-config" in [v["name"] for v in container["volumeMounts"]]:
            for volume_mount in container["volumeMounts"]:
                current_volume = get_volume_from_mount(template["spec"], volume_mount)
                if "secret" in current_volume:
                    # Extract the paths where this volume's secrets are mounted
                    secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                    parent, keys = get_mounts_part(secret, volume_mount)
                    mounted_keys += keys
                    mounted_keys_to_parents.update({k: parent for k in keys})
                elif "configMap" in current_volume:
                    # Parse config map content
                    configmap = get_configmap(templates, current_volume["configMap"]["name"])
                    parent, keys = get_mounts_part(configmap, volume_mount)
                    mounted_keys += keys
                    mounted_keys_to_parents.update({k: parent for k in keys})
    assert len(mounted_keys) > 0, f"No secret or config map is mounted in the template {template_id(template)}"
    return mounted_keys, mounted_keys_to_parents


def get_pvcs_and_empty_dirs_mount_paths(template):
    mounted_keys = []
    for container in template["spec"]["template"]["spec"]["containers"]:
        for volume_mount in container.get("volumeMounts", []):
            current_volume = get_volume_from_mount(template["spec"], volume_mount)
            if "emptyDir" in current_volume or "persistentVolumeClaim" in current_volume:
                mounted_keys.append(volume_mount["mountPath"])
    return mounted_keys


def assert_exists_according_to_hook_weight(template, hook_weight, used_by):
    # We skip any template which hook weight is higher than the current template using it
    if hook_weight is not None:
        assert "helm.sh/hook-weight" in template["metadata"].get("annotations", {}), (
            f"template {template['metadata']['name']} used by {used_by} has no hook weight"
        )
        assert int(template["metadata"]["annotations"]["helm.sh/hook-weight"]) < hook_weight, (
            f"template {template['metadata']['name']} has the same or "
            f"higher hook weight ({template['metadata']['annotations']['helm.sh/hook-weight']}) "
            f"than the current one used by {used_by} ({hook_weight})"
        )


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_secrets_consistency(templates, other_secrets):
    """
    Test to ensure that all configmaps and secrets are properly mounted and consistent across the cluster.

    This test checks if each secret and configmap is correctly associated with its respective volume and container,
    ensuring that no inconsistencies or missing configurations exist.

    The test also tries to find some configuration inconsistency. For each env, args, command, and config files,
    it will read its content and find paths matching potential mounted secrets or configmap data.
    If there's a match, it makes sure that it points to an existing data mounted in the container.
    """
    workloads = [t for t in templates if t["kind"] in ("Deployment", "StatefulSet", "Job")]
    for template in workloads:
        deployable_details = template_to_deployable_details(template)
        # Gather all containers and initContainers from the template spec
        containers = template["spec"]["template"]["spec"].get("containers", []) + template["spec"]["template"][
            "spec"
        ].get("initContainers", [])

        weight = None
        if "pre-install,pre-upgrade" in template["metadata"].get("annotations", {}).get("helm.sh/hook", ""):
            weight = int(template["metadata"]["annotations"].get("helm.sh/hook-weight", 0))

        for container in containers:
            # Determine which secrets are mounted by this container
            mounted_keys = []
            mounted_keys_to_parents = {}
            mounted_config_maps = []
            mount_paths = []
            uses_rendered_config = False

            for volume_mount in container.get("volumeMounts", []):
                current_volume = get_volume_from_mount(template["spec"], volume_mount)
                if "secret" in current_volume:
                    # Extract the paths where this volume's secrets are mounted
                    secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                    assert_exists_according_to_hook_weight(secret, weight, template["metadata"]["name"])
                    parent, keys = get_mounts_part(secret, volume_mount)
                    mount_paths.append(volume_mount["mountPath"])
                    mounted_keys += keys
                    mounted_keys_to_parents.update({k: parent for k in keys})
                elif "configMap" in current_volume:
                    # Parse config map content
                    configmap = get_configmap(templates, current_volume["configMap"]["name"])
                    assert_exists_according_to_hook_weight(configmap, weight, template["metadata"]["name"])
                    mounted_config_maps.append(configmap)
                    parent, keys = get_mounts_part(configmap, volume_mount)
                    mount_paths.append(volume_mount["mountPath"])
                    mounted_keys += keys
                    mounted_keys_to_parents.update({k: parent for k in keys})
                elif "emptyDir" in current_volume and current_volume["name"] == "rendered-config":
                    # We can't verify rendered-config, it's generated at runtime
                    uses_rendered_config = True
                    mount_paths.append(volume_mount["mountPath"])
                    if "subPath" in volume_mount:
                        keys = [volume_mount["mountPath"]]
                    else:
                        keys = [f"{volume_mount['mountPath']}/{k}" for k in get_keys_from_render_config(template)]
                    mounted_keys += keys
                    for k in keys:
                        mounted_keys_to_parents[k] = volume_mount["mountPath"]

            assert len(mounted_keys) == len(set(mounted_keys)), (
                f"Mounted key paths are not unique in {template['metadata']['name']}: {mounted_keys}"
            )
            assert len(mount_paths) == len(set(mount_paths)), (
                f"Secrets mount paths are not unique in {template['metadata']['name']}: {mounted_keys}"
            )

            # If we are checking render-config,
            # we need to look up mounted_keys in the container using the rendered-config
            if container["name"].startswith("render-config"):
                rendered_mounted_keys, rendered_mounted_keys_to_parents = get_keys_from_container_using_rendered_config(
                    template, templates, other_secrets
                )
                mounted_keys += rendered_mounted_keys
                mounted_keys_to_parents.update(rendered_mounted_keys_to_parents)

            # We look for all mountKeys
            # refers <some key> to an existing configuration somewhere
            for mounted_key in mounted_keys:
                # If for some path, the configuration cannot be made explicit
                # we add them to the list of exceptions
                # For example, nginx container uses /etc/nginx natively.
                if mounted_key in deployable_details.paths_consistency_noqa:
                    continue
                mount_path_found = False
                # Parse container commands to find paths which would match a mounted key
                if find_keys_mounts_in_content(
                    mounted_key,
                    [e.get("value", "") for e in container.get("env", [])]
                    + container.get("command", [])
                    + container.get("args", []),
                ):
                    mount_path_found = True
                else:
                    # Parse container configmaps to find paths which would match a mounted secret
                    # Make sure that paths which match are actually present in mounted secrets
                    for cm in mounted_config_maps:
                        for _, content in cm["data"].items():
                            if find_keys_mounts_in_content(
                                mounted_key,
                                [content],
                            ):
                                mount_path_found = True
                if not mount_path_found and not uses_rendered_config:
                    raise AssertionError(
                        f"{mounted_key} mounted in container {container['name']} "
                        f"but no config {','.join([cm['metadata']['name'] for cm in mounted_config_maps])} "
                        f"or env variable, or command is using it"
                    )

                # We look for all secrets mountPath parents directories in configs and commands
                # And using a regex, make sure that patterns `<parent mount path>/<some key>`
                # refers <some key> to an existing mounted secret key
                mount_path_found = False

                # Parse container commands to find paths which would match a mounted secret
                # Make sure that paths which match are actually present in mounted secrets
                if find_mount_paths_and_assert_key_is_consistent(
                    f"container {container['name']}",
                    mounted_keys,
                    mounted_keys_to_parents[mounted_key],
                    [e.get("value", "") for e in container.get("env", [])]
                    + container.get("command", [])
                    + container.get("args", []),
                    deployable_details,
                ):
                    mount_path_found = True

                # Parse container configmaps to find paths which would match a mounted secret
                # Make sure that paths which match are actually present in mounted secrets
                for cm in mounted_config_maps:
                    for data, content in cm["data"].items():
                        if find_mount_paths_and_assert_key_is_consistent(
                            f"{template_id(cm)}/{data} mounted in {container['name']}",
                            mounted_keys,
                            mounted_keys_to_parents[mounted_key],
                            [content],
                            deployable_details,
                        ):
                            mount_path_found = True
                if not mount_path_found and not uses_rendered_config:
                    raise AssertionError(
                        f"{mounted_keys_to_parents[mounted_key]} used in container {container['name']} "
                        f"but no config {','.join([cm['metadata']['name'] for cm in mounted_config_maps])} "
                        f"or env variable, or command is using it"
                    )

            filtered_mounted_config_maps = filter_mounted_path_only(template, container, mounted_config_maps)
            if uses_rendered_config:
                filtered_mounted_config_maps.append(get_virtual_config_map_from_render_config(template, templates))
            potential_paths = mounted_keys + get_pvcs_and_empty_dirs_mount_paths(template)
            for path in find_paths_in_contents(container, filtered_mounted_config_maps, deployable_details):
                if path not in deployable_details.paths_consistency_noqa:
                    mount_path_found = False
                    for potential in potential_paths:
                        if path.startswith(potential):
                            mount_path_found = True
                    assert mount_path_found, (
                        f"{path} used in container {container['name']} but not mounted in {potential_paths}"
                    )
