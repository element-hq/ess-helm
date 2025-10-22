# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
import re
from base64 import b64decode
from collections import Counter
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
from .utils import template_id, template_to_deployable_details


def node_path(parent_mount, mount_node):
    if mount_node:
        return f"{parent_mount.path}/{mount_node.node_name}"
    else:
        return parent_mount.path


def is_matrix_tools_command(container_spec: dict, subcommand: str) -> bool:
    return "/matrix-tools:" in container_spec["image"] and container_spec["args"][0] == subcommand


# A parent mount is the parent directory of a mounted file
@dataclass(frozen=True)
class ParentMount:
    path: str = field(default_factory=str, hash=True)


# A mount node is a file in a mounted directory
@dataclass(frozen=True)
class MountNode:
    node_name: str = field(default_factory=str, hash=True)
    node_data: str = field(default_factory=str)


# Source of a mounted path can be anything mounted in a container
class SourceOfMountedPaths(abc.ABC):
    @abc.abstractmethod
    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        pass

    @abc.abstractmethod
    def name(self) -> str:
        return ""


# A mounted secret will be the source of a mounted path for each secret key
@dataclass(frozen=True)
class MountedSecret(SourceOfMountedPaths):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)
    secret_name: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, volume_mount):
        assert template["kind"] == "Secret"
        # When secret data is empty, `data:` is None, so use `get_or_empty`
        template_data = get_or_empty(template, "data")
        if "subPath" in volume_mount:
            return cls(
                secret_name=template["metadata"]["name"],
                data={volume_mount["mountPath"].split("/")[-1]: template_data[volume_mount["subPath"]]},
                mount_point="/".join(volume_mount["mountPath"].split("/")[:-1]),
            )
        else:
            return cls(
                secret_name=template["metadata"]["name"], data=template_data, mount_point=volume_mount["mountPath"]
            )

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        return [
            (ParentMount(self.mount_point), MountNode(k, b64decode(v).decode("utf-8"))) for k, v in self.data.items()
        ]

    def name(self) -> str:
        return f"Secret {self.secret_name}"


# A mounted configmap will be the source of a mounted path for each configmap key
@dataclass(frozen=True)
class MountedConfigMap(SourceOfMountedPaths):
    data: dict[str, str] = field(default_factory=dict)
    mount_point: str = field(default_factory=str)
    config_map_name: str = field(default_factory=str)

    @classmethod
    def from_template(cls, template, volume_mount):
        assert template["kind"] == "ConfigMap"
        # When secret data is empty, `data:` is None, so use `get_or_empty`
        template_data = get_or_empty(template, "data")
        if "subPath" in volume_mount:
            return cls(
                config_map_name=template["metadata"]["name"],
                data={volume_mount["mountPath"].split("/")[-1]: template_data[volume_mount["subPath"]]},
                mount_point="/".join(volume_mount["mountPath"].split("/")[:-1]),
            )
        else:
            return cls(
                config_map_name=template["metadata"]["name"], data=template_data, mount_point=volume_mount["mountPath"]
            )

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        return [(ParentMount(self.mount_point), MountNode(k, v)) for k, v in self.data.items()]

    def name(self) -> str:
        return f"ConfigMap {self.config_map_name}"


# A mounted empty dir is a mutable instance of an empty dir that will be updated as we traverse containers
@dataclass()
class MountedEmptyDir(SourceOfMountedPaths):
    render_config_outputs: dict[str, str] = field(default_factory=dict)
    subcontent: tuple[str, ...] = field(default_factory=tuple)
    mount_point: str = field(default_factory=str)
    empty_dir_name: str = field(default_factory=str)

    @classmethod
    def from_template(cls, name, mount_point, content_volumes_mapping):
        return cls(
            empty_dir_name=name,
            mount_point=mount_point["mountPath"]
            if "subPath" not in mount_point
            else "/".join(mount_point["mountPath"].split("/")[:-1]),
            subcontent=content_volumes_mapping.get(mount_point["mountPath"], ()),
        )

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        mounted: list[tuple[ParentMount, MountNode | None]] = [(ParentMount(self.mount_point), None)]
        for o in self.render_config_outputs:
            mounted.append((ParentMount(self.mount_point), MountNode(o, "")))
        for node_name in self.subcontent:
            mounted.append((ParentMount(self.mount_point), MountNode(node_name, "")))
        return mounted

    def name(self) -> str:
        return f"EmptyDir {self.empty_dir_name}"


# A mounted persistent volume is the source of a mounted path only for the mount point
@dataclass(frozen=True)
class MountedPersistentVolume(SourceOfMountedPaths):
    mount_point: str = field(default_factory=str)
    subcontent: tuple[str, ...] = field(default_factory=tuple)
    pvc_name: str = field(default_factory=str)

    @classmethod
    def from_template(cls, volume, mount_point, content_volumes_mapping):
        return cls(
            pvc_name=volume["name"],
            mount_point=mount_point["mountPath"],
            subcontent=content_volumes_mapping.get(mount_point["mountPath"], ()),
        )

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        return [(ParentMount(self.mount_point), None)] + [
            (ParentMount(self.mount_point), MountNode(node_name, "")) for node_name in self.subcontent
        ]

    def name(self) -> str:
        return f"PersistentVolume {self.pvc_name}"


@dataclass(frozen=True)
class SubPathMount(SourceOfMountedPaths):
    sub_path: str = field(default_factory=str)
    source: SourceOfMountedPaths = field(default_factory=SourceOfMountedPaths)

    def get_mounted_paths(self) -> list[tuple[ParentMount, MountNode | None]]:
        filtered = []
        for mounted in self.source.get_mounted_paths():
            if mounted[1] and mounted[1].node_name == self.sub_path:
                filtered.append(mounted)
        return filtered

    def name(self) -> str:
        return f"SubPathMount({self.source.name()})"

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


## Gets all mounted files in a given container
def get_all_mounted_files(
    workload_spec, container_name, templates, other_secrets, mounted_empty_dirs: dict[str, MountedEmptyDir]
):
    def _get_content(content, kind):
        if kind in ["EmptyDir", "ConfigMap"]:
            return content
        else:
            return b64decode(content).decode("utf-8")

    found_files = {}
    for container_spec in workload_spec.get("initContainers", []) + workload_spec["containers"]:
        if container_name != container_spec["name"]:
            continue
        for volume_mount in container_spec.get("volumeMounts", []):
            current_volume = get_volume_from_mount(workload_spec, volume_mount)
            if "configMap" in current_volume:
                current_res = get_configmap(templates, current_volume["configMap"]["name"])
            elif "secret" in current_volume:
                current_res = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
            elif "emptyDir" in current_volume:
                # We create a fake resource locally to this function to find the content of the empty dir
                current_res = {
                    "kind": "EmptyDir",
                    "data": mounted_empty_dirs[current_volume["name"]].render_config_outputs,
                }
            if volume_mount.get("subPath"):
                found_files[volume_mount["mountPath"]] = _get_content(
                    current_res["data"][volume_mount["subPath"]], current_res["kind"]
                )
            else:
                for key in get_or_empty(current_res, "data"):
                    if current_res["kind"] == "ConfigMap":
                        found_files[volume_mount["mountPath"] + "/" + key] = _get_content(
                            current_res["data"][key], current_res["kind"]
                        )

    return found_files


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
        for key, content in self.data.items():
            if key in skip_path_consistency_for_files:
                continue
            paths += match_path_in_content(content)
        return paths


# A consumer which refers to files through input env values and args/command of the container
@dataclass(frozen=True)
class GenericContainerSpecPathConsumer(PathConsumer):
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    mounted_empty_dirs: dict[str, MountedEmptyDir] = field(default_factory=dict)

    @classmethod
    def from_container_spec(cls, workload_spec, container_spec, previously_mounted_empty_dirs):
        mounted_empty_dirs = {}
        for volume_mount in container_spec.get("volumeMounts", []):
            volume = get_volume_from_mount(workload_spec, volume_mount)
            if "emptyDir" in volume and volume["name"] in previously_mounted_empty_dirs:
                mounted_empty_dirs[volume["name"]] = previously_mounted_empty_dirs[volume["name"]]
        return cls(
            env={e["name"]: e["value"] for e in container_spec.get("env", [])},
            args=container_spec.get("command") or container_spec.get("args", []),
            mounted_empty_dirs=mounted_empty_dirs,
        )

    def path_is_used_in_content(self, path) -> bool:
        return find_keys_mounts_in_content(
            path,
            list(self.env.values())
            + self.args
            + [
                rendered_content
                for empty_dir in self.mounted_empty_dirs.values()
                for file, rendered_content in empty_dir.render_config_outputs.items()
            ],
        )

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in [
            v
            for v in list(self.env.values())
            + self.args
            + [
                rendered_content
                for empty_dir in self.mounted_empty_dirs.values()
                for file, rendered_content in empty_dir.render_config_outputs.items()
            ]
        ]:
            for match in re.findall(rf"(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for content in (
            list(self.env.values())
            + self.args
            + [
                rendered_content
                for empty_dir in self.mounted_empty_dirs.values()
                for file, rendered_content in empty_dir.render_config_outputs.items()
            ]
        ):
            paths += match_path_in_content(content)
        return paths


# A consumer which render-config, so will consume only files prefixed by "readfile " + the render-config input files
@dataclass(frozen=True)
class RenderConfigContainerPathConsumer(PathConsumer):
    inputs_files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_container_spec(
        cls, container_spec, workload_spec, templates, other_secrets, mutable_empty_dirs: dict[str, MountedEmptyDir]
    ):
        all_mounted_files = get_all_mounted_files(
            workload_spec, container_spec["name"], templates, other_secrets, mutable_empty_dirs
        )
        args = container_spec["args"]
        for idx, cmd in enumerate(args):
            if cmd == "-output":
                target = args[idx + 1]
                output = ParentMount("/".join(target.split("/")[:-1])), MountNode(target.split("/")[-1])
                break

        render_config_container = cls(
            inputs_files={
                f: c
                for f, c in all_mounted_files.items()
                for input_file in container_spec["args"][3:]
                if f in input_file
            },
            env={e["name"]: e["value"] for e in container_spec.get("env", [])},
        )

        # We trim readfile calls from the rendered content
        for volume_mount in container_spec.get("volumeMounts", []):
            volume = get_volume_from_mount(workload_spec, volume_mount)
            if "emptyDir" in volume and volume_mount["mountPath"] == output[0].path:
                assert "subPath" not in volume_mount, "render-config should not target a file mounted using `subPath`"
                mutable_empty_dirs[volume["name"]].render_config_outputs[output[1].node_name] = "\n".join(
                    [
                        re.sub(r"{{\s+(?:readfile\s+)(?:^|\s|\".+)\s*}}", "", content)
                        for content in render_config_container.inputs_files.values()
                    ]
                )

        return render_config_container

    # noqa: we do not check if path is used in content against render-config containers
    # as they mount all secrets that *might* be useful
    def path_is_used_in_content(self, path) -> bool:
        return True

    def get_parent_mount_lookalikes(self, paths_consistency_noqa, parent_mount: ParentMount) -> list[str]:
        lookalikes = []

        for match_in in list(self.env.values()) + list(self.inputs_files.values()):
            for match in re.findall(
                rf"(?:readfile\s+)(?:^|\s|\"){parent_mount.path}/([^\s\n\")`;,]+(?!.*noqa))", match_in
            ):
                if f"{parent_mount.path}/{match}" in paths_consistency_noqa:
                    continue
                lookalikes.append(f"{parent_mount.path}/{match}")
        return lookalikes

    def get_all_paths_in_content(self, skip_path_consistency_for_files):
        paths = []
        for key, content in self.inputs_files.items():
            if key in skip_path_consistency_for_files:
                continue
            paths += match_path_in_content("\n".join([line for line in content.splitlines() if "readfile" in line]))
        for value in self.env.values():
            paths += match_path_in_content(value)
        return paths


@dataclass
class ValidatedConfig(abc.ABC):
    @abc.abstractmethod
    def check_paths_used_in_content(self, skip_path_consistency_for_files, paths_consistency_noqa):
        pass

    @abc.abstractmethod
    def check_paths_lookalikes_matchs_source_of_mounted_paths(self, paths_consistency_noqa):
        pass

    @abc.abstractmethod
    def check_all_paths_matches_an_actual_mount(self, skip_path_consistency_for_files, paths_consistency_noqa):
        pass


# A validated configuration for a given container has a list of sources of mounted paths
# and a list of paths consumers. The test makes sure that those two are consistent
@dataclass
class ValidatedContainerConfig(ValidatedConfig):
    template_id: str
    name: str
    paths_consumers: list[PathConsumer] = field(default_factory=list)
    sources_of_mounted_paths: list[SourceOfMountedPaths] = field(default_factory=list)
    # The list of empty directories that will be muted accross the containers traversed
    # Only emptyDirs which are not using subPath can be modified
    mutable_empty_dirs: dict[str, MountedEmptyDir] = field(default_factory=dict)

    @classmethod
    def from_container_spec(
        cls,
        template_id,
        workload_spec,
        container_spec,
        weight,
        deployable_details,
        templates,
        other_secrets,
        previously_mounted_empty_dirs: dict[str, MountedEmptyDir],
    ):
        validated_config = cls(template_id=template_id, name=deployable_details.name)
        # Determine which secrets are mounted by this container
        mounted_files = []

        for volume_mount in container_spec.get("volumeMounts", []):
            current_volume = get_volume_from_mount(workload_spec, volume_mount)
            if "secret" in current_volume:
                # Extract the paths where this volume's secrets are mounted
                secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                assert_exists_according_to_hook_weight(secret, weight, validated_config.name)
                current_source_of_mount = MountedSecret.from_template(secret, volume_mount)
            elif "configMap" in current_volume:
                # Parse config map content
                configmap = get_configmap(templates, current_volume["configMap"]["name"])
                assert_exists_according_to_hook_weight(configmap, weight, validated_config.name)
                # We do not consume ConfigMaps in render-config, their configuration
                # will actually be consumed later by the container using the rendered-config
                current_source_of_mount = MountedConfigMap.from_template(configmap, volume_mount)
                if not is_matrix_tools_command(container_spec, "render-config"):
                    validated_config.paths_consumers.append(ConfigMapPathConsumer.from_configmap(configmap))
            elif "emptyDir" in current_volume:
                # An empty dir can be mounted multiple times on a container if using subPath
                # So we need to keep track of them, create them without any rendered output
                # We fill up the rendered output available to this container on the next step
                if current_volume["name"] in previously_mounted_empty_dirs:
                    current_source_of_mount = previously_mounted_empty_dirs[current_volume["name"]]
                    if "subPath" in volume_mount:
                        current_source_of_mount.mount_point = "/".join(volume_mount["mountPath"].split("/")[:-1])
                    else:
                        current_source_of_mount.mount_point = volume_mount["mountPath"]
                else:
                    current_source_of_mount = MountedEmptyDir.from_template(
                        current_volume["name"], volume_mount, deployable_details.content_volumes_mapping
                    )
                validated_config.mutable_empty_dirs[current_volume["name"]] = current_source_of_mount
            elif "persistentVolumeClaim" in current_volume:
                current_source_of_mount = MountedPersistentVolume.from_template(
                        current_volume, volume_mount, deployable_details.content_volumes_mapping
                    )
            # If we have a subPath we filter the files using a SubPathMount
            if "subPath" in volume_mount:
                validated_config.sources_of_mounted_paths.append(SubPathMount(volume_mount["subPath"],
                                                                            current_source_of_mount))
            else:
                validated_config.sources_of_mounted_paths.append(current_source_of_mount)

        mounted_files = [
            node_path(parent_mount, mount_node)
            for source in validated_config.sources_of_mounted_paths
            for parent_mount, mount_node in source.get_mounted_paths()
        ]
        assert len(mounted_files) == len(set(mounted_files)), (
            f"Mounted files are not unique in {container_spec['name']}\n"
            f"Duplicated files : { {item for item, count in Counter(mounted_files).items() if count > 1} }\n"
            f"From Mounted Sources : {validated_config.sources_of_mounted_paths}"
        )
        if is_matrix_tools_command(container_spec, "render-config"):
            render_config_consumer = RenderConfigContainerPathConsumer.from_container_spec(
                container_spec,
                workload_spec,
                templates,
                other_secrets,
                validated_config.mutable_empty_dirs,
            )
            validated_config.paths_consumers.append(render_config_consumer)
        else:
            validated_config.paths_consumers.append(
                GenericContainerSpecPathConsumer.from_container_spec(
                    workload_spec, container_spec, previously_mounted_empty_dirs
                )
            )
        return validated_config

    def check_paths_used_in_content(self, skip_path_consistency_for_files, paths_consistency_noqa):
        paths_not_found = []
        skipped_paths = []
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths():
                if (
                    node_path(parent_mount, mount_node) in paths_consistency_noqa
                    or parent_mount.path.startswith("/secrets")
                    or (mount_node
                    and mount_node.node_name in skip_path_consistency_for_files)
                ):
                    skipped_paths.append(node_path(parent_mount, mount_node))
                    continue
                for path_consumer in self.paths_consumers:
                    if path_consumer.path_is_used_in_content(node_path(parent_mount, mount_node)):
                        break
                else:
                    paths_not_found.append((node_path(parent_mount, mount_node), source))
        assert paths_not_found == [], (
            f"{self.name} : "
            f"No consumer found for paths: \n- "
            f"{
                '\n- '.join(
                    [f'{path_and_source[0]} ({path_and_source[1].name()})' for path_and_source in paths_not_found]
                )
            }\n"
            f"Skipped paths: {skipped_paths}"
        )

    def check_paths_lookalikes_matchs_source_of_mounted_paths(self, paths_consistency_noqa):
        mounted_paths = []
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths():
                mounted_paths.append(node_path(parent_mount, mount_node))
        for source in self.sources_of_mounted_paths:
            for parent_mount, _ in source.get_mounted_paths():
                if parent_mount in paths_consistency_noqa:
                    continue
                for path_consumer in self.paths_consumers:
                    for lookalikes in path_consumer.get_parent_mount_lookalikes(paths_consistency_noqa, parent_mount):
                        assert lookalikes in mounted_paths, (
                            f"{self.name} : Found path consumer mismatch in {path_consumer}"
                        )

    def check_all_paths_matches_an_actual_mount(self, skip_path_consistency_for_files, paths_consistency_noqa):
        paths_which_do_not_match = []
        for path_consumer in self.paths_consumers:
            for path in path_consumer.get_all_paths_in_content(skip_path_consistency_for_files):
                for parent_mount, mount_node in (
                    mounted
                    for mounted_path in self.sources_of_mounted_paths
                    for mounted in mounted_path.get_mounted_paths()
                ):
                    if path.startswith(node_path(parent_mount, mount_node)):
                        break
                else:
                    if path not in paths_consistency_noqa:
                        paths_which_do_not_match.append(path)
        assert paths_which_do_not_match == [], (
            f"Paths which do not match in {self.template_id}/{self.name}: {paths_which_do_not_match}. "
            f"Skipped {skip_path_consistency_for_files}\n"
            f"Looked in {self.sources_of_mounted_paths}\n"
        )


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_secrets_consistency(templates, other_secrets):
    workloads = [t for t in templates if t["kind"] in ("Deployment", "StatefulSet", "Job")]
    for template in workloads:
        # A list of empty dirs that will be updated as we traverse containers
        all_workload_empty_dirs = {}
        # Gather all containers and initContainers from the template spec
        containers = template["spec"]["template"]["spec"].get("initContainers", []) + template["spec"]["template"][
            "spec"
        ].get("containers", [])
        weight = None
        if "pre-install,pre-upgrade" in template["metadata"].get("annotations", {}).get("helm.sh/hook", ""):
            weight = int(template["metadata"]["annotations"].get("helm.sh/hook-weight", 0))

        for container_spec in containers:
            deployable_details = template_to_deployable_details(template, container_spec["name"])
            validated_container_config = ValidatedContainerConfig.from_container_spec(
                template_id(template),
                template["spec"]["template"]["spec"],
                container_spec,
                weight,
                deployable_details,
                templates,
                other_secrets,
                all_workload_empty_dirs,
            )
            validated_container_config.check_paths_used_in_content(
                deployable_details.skip_path_consistency_for_files, deployable_details.paths_consistency_noqa
            )
            validated_container_config.check_paths_lookalikes_matchs_source_of_mounted_paths(
                deployable_details.paths_consistency_noqa
            )
            validated_container_config.check_all_paths_matches_an_actual_mount(
                deployable_details.skip_path_consistency_for_files, deployable_details.paths_consistency_noqa
            )
            for name, empty_dir in validated_container_config.mutable_empty_dirs.items():
                # In the all workloads empty dirs, we copy the new render config outputs to the existing dict
                if name not in all_workload_empty_dirs:
                    all_workload_empty_dirs[name] = MountedEmptyDir(
                        mount_point=None,
                        render_config_outputs=empty_dir.render_config_outputs,
                        subcontent=empty_dir.subcontent,
                    )
