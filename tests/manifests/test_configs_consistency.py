# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
import re
from base64 import b64decode
from dataclasses import dataclass, field

import pytest

from . import DeployableDetails, secret_values_files_to_test, values_files_to_test
from .test_configs_and_mounts_consistency import (
    assert_exists_according_to_hook_weight,
    find_keys_mounts_in_content,
    get_configmap,
    get_secret,
    get_volume_from_mount,
    match_path_in_content,
)
from .utils import template_to_deployable_details


@dataclass(frozen=True)
class ParentMount:
    path: str = field(default_factory=str, hash=True)


@dataclass(frozen=True)
class MountNode:
    node_name: str = field(default_factory=str, hash=True)
    node_data: str = field(default_factory=str)


@dataclass
class SourceOfMountedPath(abc.ABC):
    @abc.abstractmethod
    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        pass


@dataclass
class MountedSecret(SourceOfMountedPath):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        assert template["kind"] == "Secret"
        return cls(data=template["data"] if template["data"] else {}, mount_point=mount_point)

    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        return {ParentMount(self.mount_point): MountNode(k, b64decode(v).decode("utf-8")) for k, v in self.data.items()}


@dataclass
class MountedConfigMap(SourceOfMountedPath):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        assert template["kind"] == "ConfigMap"
        return cls(data=template["data"], mount_point=mount_point)

    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        return {ParentMount(self.mount_point): MountNode(k, v) for k, v in self.data.items()}


@dataclass
class MountedRenderedConfigEmptyDir(SourceOfMountedPath):
    render_config_outputs: list[str] = field(default_factory=list)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_workload_spec(cls, workload_spec, mount_point):
        mounted_rendered_config_empty_dir = cls()
        for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
            if "render-config" in container_spec["name"]:
                args = container_spec.get("args") or container_spec["command"][1:]
                for idx, cmd in enumerate(args):
                    if cmd == "-output":
                        mounted_rendered_config_empty_dir.render_config_outputs.append(args[idx + 1].split("/")[-1])
        mounted_rendered_config_empty_dir.mount_point = mount_point
        return mounted_rendered_config_empty_dir

    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        # Mount node data is empty in tests as it is generated at runtime
        print(self.render_config_outputs)
        return {ParentMount(self.mount_point): MountNode(o, "") for o in self.render_config_outputs}


@dataclass
class MountedPersistentVolume(SourceOfMountedPath):
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        return cls(mount_point=mount_point)

    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        return {ParentMount(self.mount_point): MountNode("", "")}


@dataclass
class MountedEmptyDir(SourceOfMountedPath):
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        return cls(mount_point=mount_point)

    def get_mounted_paths(self) -> dict[ParentMount, MountNode]:
        return {ParentMount(self.mount_point): MountNode("", "")}


# This is something consuming paths that should through mount points
@dataclass()
class PathConsumer(abc.ABC):
    # Look in the consumer configuration and return strings that look like a ParentMount
    @abc.abstractmethod
    def get_parent_mount_lookalikes(
        self, deployable_details: DeployableDetails, parent_mount: ParentMount
    ) -> list[str]:
        pass

    # Look for all potential paths
    @abc.abstractmethod
    def get_all_paths_in_content(self, skip_path_consistency_for_files) -> list[str]:
        pass


@dataclass
class RenderedConfigPathConsumer(PathConsumer):
    inputs_files: dict[str, str] = field(default_factory=dict)

    def path_is_used_in_content(self, path) -> bool:
        return any(find_keys_mounts_in_content(path, [content]) for content in self.inputs_files.values())

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for content in self.inputs_files.values():
            paths += match_path_in_content(content)
        return paths

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in [v for v in self.inputs_files.values()]:
            for match in re.findall(rf"(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    @classmethod
    def from_workload_spec(cls, workload_spec, templates, other_secrets):
        potential_input_files = {}
        rendered_config_path_consumer = cls()
        for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
            if "render-config" in container_spec["name"]:
                for volume_mount in container_spec["volumeMounts"]:
                    current_volume = get_volume_from_mount(workload_spec, volume_mount)
                    if "configMap" in current_volume:
                        current_config_map = get_configmap(templates, current_volume["configMap"]["name"])
                        if volume_mount.get("subPath"):
                            potential_input_files[volume_mount["mountPath"] + "/" + volume_mount["subPath"]] = (
                                current_config_map["data"][volume_mount["subPath"]]
                            )
                        else:
                            for key in current_config_map["data"]:
                                potential_input_files[volume_mount["mountPath"] + "/" + key] = current_config_map[
                                    "data"
                                ][key]
                args = container_spec.get("args") or container_spec["command"][1:]
                source_files = args[3:]
                for p, k in potential_input_files.items():
                    if p in source_files:
                        rendered_config_path_consumer.inputs_files[p] = k
        return rendered_config_path_consumer


class ConfigMapPathConsumer(PathConsumer):
    data: dict[str, str] = field(default_factory=dict)

    def path_is_used_in_content(self, path) -> bool:
        return any(find_keys_mounts_in_content(path, [content]) for _, content in self.data.items())

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in [v for v in self.data.values()]:
            for match in re.findall(rf"(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for content in self.inputs_files.values():
            paths += match_path_in_content(content)
        return paths


@dataclass
class ContainerSpecPathConsumer(PathConsumer):
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)

    @classmethod
    def from_container_spec(cls, container_spec):
        return cls(
            env={e["name"]: e["value"] for e in container_spec.get("env", [])},
            args=container_spec.get("command", []) + container_spec.get("args", []),
        )

    def path_is_used_in_content(self, path) -> bool:
        return any(find_keys_mounts_in_content(path, [content]) for content in list(self.env.values()) + self.args)

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in [v for v in list(self.env.values()) + self.args]:
            for match in re.findall(rf"(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for content in list(self.env.values()) + self.args:
            paths += match_path_in_content(content)
        return paths


# A validated configuration for a given container has a list of sources of mounted paths
# and a list of paths consumers. The test makes sure that those two are consistent
@dataclass
class ValidatedContainerConfig:
    name: str
    paths_consumers: list[PathConsumer] = field(default_factory=list)
    sources_of_mounted_paths: list[SourceOfMountedPath] = field(default_factory=list)

    @classmethod
    def from_workload_spec(cls, name, workload_spec, weight, deployable_details, templates, other_secrets):
        validated_config = cls(name=name)
        for container_spec in workload_spec["containers"] + workload_spec.get("initContainers", []):
            # Determine which secrets are mounted by this container
            mounted_keys = []
            mount_paths = []

            for volume_mount in container_spec.get("volumeMounts", []):
                current_volume = get_volume_from_mount(workload_spec, volume_mount)
                if "secret" in current_volume:
                    # Extract the paths where this volume's secrets are mounted
                    secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                    assert_exists_according_to_hook_weight(secret, weight, name)
                    validated_config.sources_of_mounted_paths.append(
                        MountedSecret.from_template(secret, volume_mount["mountPath"])
                    )
                elif "configMap" in current_volume:
                    # Parse config map content
                    configmap = get_configmap(templates, current_volume["configMap"]["name"])
                    assert_exists_according_to_hook_weight(configmap, weight, name)
                    validated_config.sources_of_mounted_paths.append(
                        MountedConfigMap.from_template(configmap, volume_mount["mountPath"])
                    )
                    if container_spec["name"] == name:
                        validated_config.paths_consumers.append(
                            ConfigMapPathConsumer.from_container_spec(container_spec)
                        )
                elif "emptyDir" in current_volume and current_volume["name"] == "rendered-config":
                    validated_config.sources_of_mounted_paths.append(
                        MountedRenderedConfigEmptyDir.from_workload_spec(workload_spec, volume_mount["mountPath"])
                    )
                    if container_spec["name"] == name:
                        validated_config.paths_consumers.append(
                            RenderedConfigPathConsumer.from_workload_spec(workload_spec, templates, other_secrets)
                        )

            mounted_keys = [
                parent_mount.path + "/" + mount_node.node_name
                for source in validated_config.sources_of_mounted_paths
                for parent_mount, mount_node in source.get_mounted_paths().items()
            ]
            mount_paths = [
                parent_mount.path
                for source in validated_config.sources_of_mounted_paths
                for parent_mount in source.get_mounted_paths()
            ]

            assert len(mounted_keys) == len(set(mounted_keys)), (
                f"Mounted key paths are not unique in {name}: {mounted_keys}"
            )
            assert len(mount_paths) == len(set(mount_paths)), (
                f"Secrets mount paths are not unique in {name}: {mounted_keys}"
            )
            if container_spec["name"] == name:
                validated_config.paths_consumers.append(ContainerSpecPathConsumer.from_container_spec(container_spec))
        return validated_config

    def check_paths_used_in_content(self, paths_consistency_noqa):
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths().items():
                if parent_mount in paths_consistency_noqa:
                    continue
                for path_consumer in self.paths_consumers:
                    if path_consumer.path_is_used_in_content(f"{parent_mount.path}/{mount_node.node_name}"):
                        return True

    def check_paths_lookalikes_matchs_source_of_mounted_paths(self, paths_consistency_noqa):
        mounted_paths = []
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths().items():
                if parent_mount in paths_consistency_noqa:
                    continue
                mounted_paths.append(f"{parent_mount.path}/{mount_node.node_name}")
        for path_consumer in self.paths_consumers:
            for lookalikes in path_consumer.get_parent_mount_lookalikes(paths_consistency_noqa, parent_mount):
                assert lookalikes in mounted_paths

    def check_all_paths_matches_an_actual_mount(self, skip_path_consistency_for_files):
        all_paths_matches = True
        for path_consumer in self.paths_consumers:
            for path in path_consumer.get_all_paths_in_content(skip_path_consistency_for_files):
                for mounted_path in self.sources_of_mounted_paths:
                    for parent_mount, mount_node in mounted_path.get_mounted_paths().items():
                        if path.startswith(parent_mount.path + "/" + mount_node.node_name):
                            all_paths_matches = False
        return all_paths_matches


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_secrets_consistency(templates, other_secrets):
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

        for container_spec in containers:
            validated_container_config = ValidatedContainerConfig.from_workload_spec(
                container_spec["name"],
                template["spec"]["template"]["spec"],
                weight,
                deployable_details,
                templates,
                other_secrets,
            )
            validated_container_config.check_paths_used_in_content(deployable_details.paths_consistency_noqa)
            validated_container_config.check_paths_lookalikes_matchs_source_of_mounted_paths(
                deployable_details.paths_consistency_noqa
            )
            validated_container_config.check_all_paths_matches_an_actual_mount(
                deployable_details.paths_consistency_noqa
            )
