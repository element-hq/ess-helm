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
    get_or_empty,
    get_secret,
    get_volume_from_mount,
    match_path_in_content,
)
from .utils import template_to_deployable_details


## Gets all mounted files in a given container from the ConfigMaps referenced by the volume mounts
def get_all_mounted_files(workload_spec, container_name, templates):
    found_files = {}
    for container_spec in workload_spec["containers"] + workload_spec.get("initContainers", {}):
        for volume_mount in container_spec.get("volumeMounts", []):
            current_volume = get_volume_from_mount(workload_spec, volume_mount)
            if "configMap" in current_volume:
                current_config_map = get_configmap(templates, current_volume["configMap"]["name"])
                if volume_mount.get("subPath"):
                    found_files[volume_mount["mountPath"] + "/" + volume_mount["subPath"]] = current_config_map["data"][
                        volume_mount["subPath"]
                    ]
                else:
                    for key in current_config_map["data"]:
                        found_files[volume_mount["mountPath"] + "/" + key] = current_config_map["data"][key]
    return found_files


# A parent mount is the parent directory of a mounted file
@dataclass(frozen=True)
class ParentMount:
    path: str = field(default_factory=str, hash=True)


# A mount node is a file in a mounted directory
@dataclass(frozen=True)
class MountNode:
    node_name: str = field(default_factory=str, hash=True)
    node_data: str = field(default_factory=str)


# Source of a mounted path can be anything mounted in a container
@dataclass(frozen=True)
class SourceOfMountedPaths(abc.ABC):
    @abc.abstractmethod
    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        pass


# A mounted secret will be the source of a mounted path for each secret key
@dataclass(frozen=True)
class MountedSecret(SourceOfMountedPaths):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, volume_mount):
        assert template["kind"] == "Secret"
        # When secret data is empty, `data:` is None, so use `get_or_empty`
        template_data = get_or_empty(template, "data")
        if "subPath" in volume_mount:
            return cls(
                data={volume_mount["subPath"]: template_data[volume_mount["subPath"]]},
                mount_point="/".join(volume_mount["mountPath"].split("/")[:-1]),
            )
        else:
            return cls(data=template_data, mount_point=volume_mount["mountPath"])

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        return [
            (ParentMount(self.mount_point), MountNode(k, b64decode(v).decode("utf-8"))) for k, v in self.data.items()
        ]


# A mounted configmap will be the source of a mounted path for each configmap key
@dataclass(frozen=True)
class MountedConfigMap(SourceOfMountedPaths):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, volume_mount):
        assert template["kind"] == "ConfigMap"
        # When secret data is empty, `data:` is None, so use `get_or_empty`
        template_data = get_or_empty(template, "data")
        if "subPath" in volume_mount:
            return cls(
                data={volume_mount["mountPath"].split("/")[-1]: template_data[volume_mount["subPath"]]},
                mount_point="/".join(volume_mount["mountPath"].split("/")[:-1]),
            )
        else:
            return cls(data=template_data, mount_point=volume_mount["mountPath"])

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        return [(ParentMount(self.mount_point), MountNode(k, v)) for k, v in self.data.items()]


# A mounted rendered configmap will be the source of a mounted path
# For each render-config-* container output
@dataclass(frozen=True)
class MountedRenderedConfigEmptyDir(SourceOfMountedPaths):
    render_config_outputs: set[str] = field(default_factory=set)
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_workload_spec(cls, workload_spec, volume_mount):
        outputs = []
        for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
            if "render-config" in container_spec["name"]:
                args = container_spec.get("args") or container_spec["command"][1:]
                for idx, cmd in enumerate(args):
                    if cmd == "-output":
                        outputs.append(args[idx + 1].split("/")[-1])
                        assert len(outputs) == len(set(outputs)), "multiple render-config are rendering the same files"
        if "subPath" in volume_mount:
            return cls(
                mount_point="/".join(volume_mount["mountPath"].split("/")[:-1]),
                render_config_outputs=set(
                    volume_mount["mountPath"].split("/")[-1] for o in outputs if volume_mount["subPath"].endswith(o)
                ),
            )
        else:
            return cls(mount_point=volume_mount["mountPath"], render_config_outputs=set(outputs))

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        return [(ParentMount(self.mount_point), MountNode(o, "")) for o in self.render_config_outputs]


# A mounted persistent volume is the source of a mounted path only for the mount point
@dataclass(frozen=True)
class MountedPersistentVolume(SourceOfMountedPaths):
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        return cls(mount_point=mount_point)

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        return [(ParentMount(self.mount_point), MountNode("", ""))]


# A mounted empty dir is the source of a mounted path only for the mount point
@dataclass(frozen=True)
class MountedEmptyDir(SourceOfMountedPaths):
    mount_point: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, mount_point):
        return cls(mount_point=mount_point)

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode]]:
        return [(ParentMount(self.mount_point), MountNode("", ""))]


# This is something consuming paths that should be available through mount points
@dataclass(frozen=True)
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


# A consumer which uses as input the files rendered by render-config containers
@dataclass(frozen=True)
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
    def from_workload_spec(cls, workload_spec, templates):
        potential_input_files = {}
        inputs_files = {}
        for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
            if container_spec["name"].startswith("render-config"):
                potential_input_files = get_all_mounted_files(workload_spec, container_spec["name"], templates)
                args = container_spec.get("args") or container_spec["command"][1:]
                source_files = args[3:]
                for p, k in potential_input_files.items():
                    if p in source_files:
                        inputs_files[p] = k
        return cls(inputs_files=inputs_files)


# A consumer which uses as input the files contained in the mounted configmaps
@dataclass(frozen=True)
class ConfigMapPathConsumer(PathConsumer):
    data: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_configmap(cls, configmap):
        return cls(data=get_or_empty(configmap, "data"))

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
        for content in self.data.values():
            paths += match_path_in_content(content)
        return paths

# A consumer which refers to files through input env values and args/command of the container
@dataclass(frozen=True)
class GenericContainerSpecPathConsumer(PathConsumer):
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


# A consumer which render-config, so will consume only files prefixed by "readfile " + the render-config input files
@dataclass(frozen=True)
class RenderConfigContainerPathConsumer(PathConsumer):
    inputs_files: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_container_spec(cls, container_spec, workload_spec, templates):
        args = container_spec.get("args") or container_spec["command"][1:]
        all_mounted_files = get_all_mounted_files(workload_spec, container_spec["name"], templates)
        return cls(
            inputs_files={f: c for f, c in all_mounted_files.items() for input_file in args[3:] if f in input_file}
        )

    def path_is_used_in_content(self, path) -> bool:
        return any(find_keys_mounts_in_content(path, [content]) for content in list(self.inputs_files.values()))

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in [v for v in self.inputs_files.values()]:
            for match in re.findall(
                rf"(?:readfile\s+)(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in
            ):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for content in list(self.env.values()) + self.args:
            paths += match_path_in_content(content)
        return paths


@dataclass
class ValidatedConfig(abc.ABC):
    @abc.abstractmethod
    def check_paths_used_in_content(self, paths_consistency_noqa):
        pass

    @abc.abstractmethod
    def check_paths_lookalikes_matchs_source_of_mounted_paths(self, paths_consistency_noqa):
        pass

    @abc.abstractmethod
    def check_all_paths_matches_an_actual_mount(self, skip_path_consistency_for_files):
        pass


# A validated configuration for a given container has a list of sources of mounted paths
# and a list of paths consumers. The test makes sure that those two are consistent
@dataclass
class ValidatedContainerConfig(ValidatedConfig):
    name: str
    paths_consumers: list[PathConsumer] = field(default_factory=list)
    sources_of_mounted_paths: list[SourceOfMountedPaths] = field(default_factory=list)

    @classmethod
    def from_workload_spec(cls, name, workload_spec, weight, deployable_details, templates, other_secrets):
        validated_config = cls(name=name)
        for container_spec in workload_spec["containers"] + workload_spec.get("initContainers", []):
            if container_spec["name"] != name:
                continue
            # Determine which secrets are mounted by this container
            mounted_files = []
            has_rendered_config = False

            for volume_mount in container_spec.get("volumeMounts", []):
                current_volume = get_volume_from_mount(workload_spec, volume_mount)
                if "secret" in current_volume:
                    # Extract the paths where this volume's secrets are mounted
                    secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                    assert_exists_according_to_hook_weight(secret, weight, name)
                    validated_config.sources_of_mounted_paths.append(MountedSecret.from_template(secret, volume_mount))
                elif "configMap" in current_volume:
                    # Parse config map content
                    configmap = get_configmap(templates, current_volume["configMap"]["name"])
                    assert_exists_according_to_hook_weight(configmap, weight, name)
                    # We do not consume ConfigMaps in render-config, their configuration
                    # will actually be consumed later by the container using the rendered-config
                    if not container_spec["name"].startswith("render-config"):
                        validated_config.sources_of_mounted_paths.append(
                            MountedConfigMap.from_template(configmap, volume_mount)
                        )
                    validated_config.paths_consumers.append(ConfigMapPathConsumer.from_configmap(configmap))
                elif (
                    "emptyDir" in current_volume
                    and current_volume["name"] == "rendered-config"
                    and not container_spec["name"].startswith("render-config")
                ):
                    has_rendered_config = True
                    validated_config.sources_of_mounted_paths.append(
                        MountedRenderedConfigEmptyDir.from_workload_spec(workload_spec, volume_mount)
                    )

            mounted_files = [
                parent_mount.path + "/" + mount_node.node_name
                for source in validated_config.sources_of_mounted_paths
                for parent_mount, mount_node in source.get_mounted_paths()
            ]

            assert len(mounted_files) == len(set(mounted_files)), (
                f"Mounted files are not unique in {name}: {validated_config.sources_of_mounted_paths}"
            )
            if container_spec["name"] == name:
                if has_rendered_config:
                    validated_config.paths_consumers.append(
                        RenderedConfigPathConsumer.from_workload_spec(workload_spec, templates)
                    )
                else:
                    validated_config.paths_consumers.append(
                        GenericContainerSpecPathConsumer.from_container_spec(container_spec)
                    )
        return validated_config

    def check_paths_used_in_content(self, paths_consistency_noqa):
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths():
                if parent_mount in paths_consistency_noqa:
                    continue
                for path_consumer in self.paths_consumers:
                    if path_consumer.path_is_used_in_content(f"{parent_mount.path}/{mount_node.node_name}"):
                        return True

    def check_paths_lookalikes_matchs_source_of_mounted_paths(self, paths_consistency_noqa):
        mounted_paths = []
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths():
                mounted_paths.append(f"{parent_mount.path}/{mount_node.node_name}")
        for source in self.sources_of_mounted_paths:
            for parent_mount, _ in source.get_mounted_paths():
                if parent_mount in paths_consistency_noqa:
                    continue
                for path_consumer in self.paths_consumers:
                    for lookalikes in path_consumer.get_parent_mount_lookalikes(paths_consistency_noqa, parent_mount):
                        assert lookalikes in mounted_paths, (
                            f"{self.name} : Found path consumer mismatch in {path_consumer}"
                        )

    def check_all_paths_matches_an_actual_mount(self, skip_path_consistency_for_files):
        all_paths_matches = True
        for path_consumer in self.paths_consumers:
            for path in path_consumer.get_all_paths_in_content(skip_path_consistency_for_files):
                for mounted_path in self.sources_of_mounted_paths:
                    for parent_mount, mount_node in mounted_path.get_mounted_paths():
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
