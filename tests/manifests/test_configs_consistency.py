# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
import re
from base64 import b64decode, b64encode
from collections import Counter
from collections.abc import Generator
from dataclasses import dataclass, field

import pytest

from . import DeployableDetails, secret_values_files_to_test, values_files_to_test
from .utils import (
    get_or_empty,
    template_id,
    template_to_deployable_details,
    workload_spec_containers,
)


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


def get_configmap(templates, other_configmaps, configmap_name):
    """
    Get the content of a ConfigMap with the given name.
    :param configmap_name: The name of the ConfigMap to retrieve.
    :return: A string containing the content of the ConfigMap, or an empty string if not found.
    """
    for t in templates + other_configmaps:
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
        if t["kind"] == "Certificate" and t["spec"]["secretName"] == secret_name:
            return {
                "kind": "Secret",
                "metadata": {
                    "name": secret_name,
                    "namespace": t["metadata"]["namespace"],
                },
                "data": {"tls.crt": b64encode(b"some-certificate"), "tls.key": b64encode(b"some-key")},
            }
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


def match_path_in_content(content: str) -> list[str]:
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


def find_path_in_content(path, matches_in: list[str]):
    for match_in in matches_in:
        for match in re.findall(re.escape(path), match_in):
            if match:
                return True
    return False


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


@dataclass(frozen=True)
class MountPath:
    parent_mount: ParentMount = field(default_factory=ParentMount)
    mount_node: MountNode | None = field(default_factory=MountNode)

    def __str__(self):
        if self.mount_node:
            return f"{self.parent_mount.path}/{self.mount_node.node_name}"
        else:
            return self.parent_mount.path


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
        # When configmap data is empty, `data:` is None, so use `get_or_empty`
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
    # Look for all potential paths
    @abc.abstractmethod
    def get_all_paths_in_content(self, deployable_details: DeployableDetails) -> list[str]:
        pass

    # Mutate empty dirs after the container has been consistency-checked
    @abc.abstractmethod
    def mutate_empty_dirs(self, container_spec, workload_spec, mutable_empty_dirs: dict[str, MountedEmptyDir]):
        pass

    # Check if the path is used in the container
    @abc.abstractmethod
    def path_is_used_in_content(self, path) -> bool:
        pass


## Gets all mounted files in a render-config container
def get_all_mounted_files(
    workload_spec,
    container_spec,
    templates,
    other_secrets,
    other_configmaps,
    mounted_empty_dirs: dict[str, MountedEmptyDir],
):
    def _get_content(content, kind):
        if kind in ["EmptyDir", "ConfigMap"]:
            return content
        else:
            return b64decode(content).decode("utf-8")

    found_files = {}
    for volume_mount in container_spec.get("volumeMounts", []):
        current_volume = get_volume_from_mount(workload_spec, volume_mount)
        if "configMap" in current_volume:
            current_res = get_configmap(templates, other_configmaps, current_volume["configMap"]["name"])
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
        return any(find_path_in_content(path, [content]) for _, content in self.data.items())

    def get_all_paths_in_content(self, deployable_details: DeployableDetails) -> list[str]:
        paths = []
        for key, content in self.data.items():
            if key in deployable_details.skip_path_consistency_for_files:
                continue
            paths += match_path_in_content(content)
        return paths

    def mutate_empty_dirs(self, container_spec, workload_spec, mutable_empty_dirs: dict[str, MountedEmptyDir]):
        pass


# A consumer which refers to files through input env values and args/command of the container
@dataclass(frozen=True)
class GenericContainerSpecPathConsumer(PathConsumer):
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    mounted_empty_dirs: dict[str, MountedEmptyDir] = field(default_factory=dict)
    exec_properties: dict[str, str] = field(default_factory=dict)

    def _empty_dir_rendered_content(self) -> list[str]:
        return [
            rendered_content
            for empty_dir in self.mounted_empty_dirs.values()
            for rendered_content in empty_dir.render_config_outputs.values()
        ]

    def _all_container_content(self) -> list[str]:
        return (
            list(self.env.values())
            + list(self.exec_properties.values())
            + list(self.args)
            + self._empty_dir_rendered_content()
        )

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
            exec_properties={
                p: "\n".join(container_spec[p]["exec"]["command"])
                for p in ("startupProbe", "livenessProbe", "readinessProbe")
                if container_spec.get(p, {}).get("exec", {})
            }
            | {
                p: "\n".join(container_spec["lifecycle"][p]["exec"]["command"])
                for p in ("postStart", "preStop")
                if container_spec.get("lifecycle", {}).get(p, {}).get("exec", {})
            },
            mounted_empty_dirs=mounted_empty_dirs,
        )

    def path_is_used_in_content(self, path) -> bool:
        return find_path_in_content(path, self._all_container_content())

    def get_all_paths_in_content(self, deployable_details: DeployableDetails):
        paths = []
        for content in self._all_container_content():
            paths += match_path_in_content(content)
        return paths

    def mutate_empty_dirs(self, container_spec, workload_spec, mutable_empty_dirs: dict[str, MountedEmptyDir]):
        pass


# A consumer which render-config, so will consume only files prefixed by "readfile " + the render-config input files
@dataclass(frozen=True)
class RenderConfigContainerPathConsumer(PathConsumer):
    inputs_files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    output: MountPath = field(default_factory=MountPath)

    @classmethod
    def from_container_spec(
        cls,
        container_spec,
        workload_spec,
        templates,
        other_secrets,
        other_configmaps,
        mutable_empty_dirs: dict[str, MountedEmptyDir],
    ):
        all_mounted_files = get_all_mounted_files(
            workload_spec, container_spec, templates, other_secrets, other_configmaps, mutable_empty_dirs
        )
        args = container_spec["args"]
        for idx, cmd in enumerate(args):
            if cmd == "-output":
                target = args[idx + 1]
                output = MountPath(ParentMount("/".join(target.split("/")[:-1])), MountNode(target.split("/")[-1]))
                break

        render_config_container = cls(
            inputs_files={
                input_file: all_mounted_files[input_file] for input_file in container_spec["args"][idx + 2 :]
            },
            env={e["name"]: e["value"] for e in container_spec.get("env", [])},
            output=output,
        )

        return render_config_container

    def mutate_empty_dirs(self, container_spec, workload_spec, mutable_empty_dirs: dict[str, MountedEmptyDir]):
        # We trim readfile calls from the rendered content
        for volume_mount in container_spec.get("volumeMounts", []):
            volume = get_volume_from_mount(workload_spec, volume_mount)
            if "emptyDir" in volume and volume_mount["mountPath"] == self.output.parent_mount.path:
                assert "subPath" not in volume_mount, "render-config should not target a file mounted using `subPath`"
                assert self.output.mount_node is not None
                mutable_empty_dirs[volume["name"]].render_config_outputs[self.output.mount_node.node_name] = "\n".join(
                    [
                        re.sub(r"{{\s+(?:readfile\s+)(?:^|\s|\".+)\s*}}", "", content)
                        for content in self.inputs_files.values()
                    ]
                )

    def path_is_used_in_content(self, path) -> bool:
        return (
            find_path_in_content(
                path,
                [str(self.output)]
                + list(self.env.values())
                + list(self.inputs_files.keys())
                + list(self.inputs_files.values()),
            )
            # for now we deliberately mount too many files in config-templates
            or path.startswith("/conf")
            # we also deliberately ignore files which are in the same directory as our output
            # as we are most certainly accumulating files here
            or path.startswith(self.output.parent_mount.path)
        )

    def get_all_paths_in_content(self, deployable_details: DeployableDetails):
        paths = []
        for key, content in self.inputs_files.items():
            if key in deployable_details.skip_path_consistency_for_files:
                continue
            paths += match_path_in_content("\n".join([line for line in content.splitlines() if "readfile" in line]))
        for value in self.env.values():
            paths += match_path_in_content(value)
        return paths


@dataclass
class ValidatedConfig(abc.ABC):
    @abc.abstractmethod
    def check_mounted_files_unique(self, deployable_details: DeployableDetails):
        pass

    @abc.abstractmethod
    def check_paths_used_in_content(self, deployable_details: DeployableDetails):
        pass

    @abc.abstractmethod
    def check_all_paths_matches_an_actual_mount(self, deployable_details: DeployableDetails):
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
    deployable_details: DeployableDetails = field(default=None)  # type: ignore[assignment]

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
        other_configmaps,
        previously_mounted_empty_dirs: dict[str, MountedEmptyDir],
    ):
        validated_config = cls(
            template_id=template_id, name=container_spec["name"], deployable_details=deployable_details
        )

        for volume_mount in container_spec.get("volumeMounts", []):
            current_volume = get_volume_from_mount(workload_spec, volume_mount)
            if "secret" in current_volume:
                # Extract the paths where this volume's secrets are mounted
                secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                assert_exists_according_to_hook_weight(secret, weight, validated_config.name)
                current_source_of_mount = MountedSecret.from_template(secret, volume_mount)
            elif "configMap" in current_volume:
                # Parse config map content
                configmap = get_configmap(templates, other_configmaps, current_volume["configMap"]["name"])
                assert_exists_according_to_hook_weight(configmap, weight, validated_config.name)
                current_source_of_mount = MountedConfigMap.from_template(configmap, volume_mount)
                if not is_matrix_tools_command(container_spec, "render-config"):
                    # We only consume ConfigMaps in render-config
                    # We do not need a SecretPathConsumer as we do not have configuration stored in secrets
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
                validated_config.sources_of_mounted_paths.append(
                    SubPathMount(volume_mount["subPath"], current_source_of_mount)
                )
            else:
                validated_config.sources_of_mounted_paths.append(current_source_of_mount)

        if is_matrix_tools_command(container_spec, "render-config"):
            render_config_consumer = RenderConfigContainerPathConsumer.from_container_spec(
                container_spec,
                workload_spec,
                templates,
                other_secrets,
                other_configmaps,
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

    def check_mounted_files_unique(self):
        mounted_files = [
            str(MountPath(parent_mount, mount_node))
            for source in self.sources_of_mounted_paths
            for parent_mount, mount_node in source.get_mounted_paths()
        ]
        assert len(mounted_files) == len(set(mounted_files)), (
            f"{self.template_id}/{self.name} : "
            f"Mounted files are not unique \n"
            f"Duplicated files : { {item for item, count in Counter(mounted_files).items() if count > 1} }\n"
            f"From Mounted Sources : {self.sources_of_mounted_paths}"
        )

    def check_paths_used_in_content(self):
        paths_not_found = []
        skipped_paths = []
        for source in self.sources_of_mounted_paths:
            for parent_mount, mount_node in source.get_mounted_paths():
                if (
                    str(MountPath(parent_mount, mount_node))
                    in self.deployable_details.ignore_unreferenced_mounts.get(self.name, [])
                    # for now we deliberately mount too many secrets in /secrets
                    or parent_mount.path.startswith("/secrets")
                    or (mount_node and mount_node.node_name in self.deployable_details.skip_path_consistency_for_files)
                ):
                    skipped_paths.append(str(MountPath(parent_mount, mount_node)))
                    continue
                for path_consumer in self.paths_consumers:
                    if path_consumer.path_is_used_in_content(str(MountPath(parent_mount, mount_node))):
                        break
                else:
                    paths_not_found.append((str(MountPath(parent_mount, mount_node)), source))
        assert paths_not_found == [], (
            f"{self.template_id}/{self.name} : "
            f"No consumer found for paths: \n- "
            f"{
                '\n- '.join(
                    [f'{path_and_source[0]} ({path_and_source[1].name()})' for path_and_source in paths_not_found]
                )
            }\n"
            f"Skipped paths: {skipped_paths}"
        )

    def check_all_paths_matches_an_actual_mount(self):
        paths_which_do_not_match = []
        for path_consumer in self.paths_consumers:
            for path in path_consumer.get_all_paths_in_content(self.deployable_details):
                for parent_mount, mount_node in (
                    mounted
                    for mounted_path in self.sources_of_mounted_paths
                    for mounted in mounted_path.get_mounted_paths()
                ):
                    if path.startswith(str(MountPath(parent_mount, mount_node))):
                        break
                else:
                    if path not in self.deployable_details.ignore_paths_mismatches.get(self.name, []):
                        paths_which_do_not_match.append(path)
        assert paths_which_do_not_match == [], (
            f"Paths which do not match an actual file in {self.template_id}/{self.name}: {paths_which_do_not_match}. "
            f"Skipped {self.deployable_details.skip_path_consistency_for_files}\n"
            f"Looked in {self.sources_of_mounted_paths}\n"
        )

    def mutate_empty_dirs(self, container_spec, workload_spec):
        for consumer in self.paths_consumers:
            consumer.mutate_empty_dirs(container_spec, workload_spec, self.mutable_empty_dirs)


def traverse_containers(templates, other_secrets, other_configmaps) -> Generator[ValidatedContainerConfig]:
    workloads = [t for t in templates if t["kind"] in ("Deployment", "StatefulSet", "Job")]
    for template in workloads:
        all_workload_empty_dirs: dict[str, MountedEmptyDir] = {}
        # Gather all containers and initContainers from the template spec
        workload_spec = template["spec"]["template"]["spec"]
        weight = None
        if "pre-install,pre-upgrade" in template["metadata"].get("annotations", {}).get("helm.sh/hook", ""):
            weight = int(template["metadata"]["annotations"].get("helm.sh/hook-weight", 0))

        for container_spec in workload_spec_containers(workload_spec):
            deployable_details = template_to_deployable_details(template, container_spec["name"])
            validated_container_config = ValidatedContainerConfig.from_container_spec(
                template_id(template),
                workload_spec,
                container_spec,
                weight,
                deployable_details,
                templates,
                other_secrets,
                other_configmaps,
                all_workload_empty_dirs,
            )
            yield validated_container_config
            validated_container_config.mutate_empty_dirs(container_spec, workload_spec)
            for name, empty_dir in validated_container_config.mutable_empty_dirs.items():
                # In the all workloads empty dirs, we copy the new render config outputs to the existing dict
                if name not in all_workload_empty_dirs:
                    all_workload_empty_dirs[name] = MountedEmptyDir(
                        render_config_outputs=empty_dir.render_config_outputs,
                        subcontent=empty_dir.subcontent,
                    )


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_mounted_files_unique(templates, other_secrets, other_configmaps):
    # A list of empty dirs that will be updated as we traverse containers
    for validated_container_config in traverse_containers(templates, other_secrets, other_configmaps):
        validated_container_config.check_mounted_files_unique()


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_any_mounted_path_is_used_in_content(templates, other_secrets, other_configmaps):
    for validated_container_config in traverse_containers(templates, other_secrets, other_configmaps):
        validated_container_config.check_paths_used_in_content()


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_any_path_found_matches_an_actual_mount(templates, other_secrets, other_configmaps):
    for validated_container_config in traverse_containers(templates, other_secrets, other_configmaps):
        validated_container_config.check_all_paths_matches_an_actual_mount()
