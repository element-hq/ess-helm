# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
from dataclasses import dataclass, field
from enum import Enum
from base64 import b64decode
from typing import Any
import re

from . import DeployableDetails
from .test_configs_and_mounts_consistency import get_volume_from_mount, get_configmap, get_secret, find_keys_mounts_in_content, assert_exists_according_to_hook_weight


@dataclass
class ParentMount():
  path: str = field(default_factory=str)

@dataclass
class MountNode():
  node_name: str = field(default_factory=str)
  node_data: str = field(default_factory=str)

@dataclass
class SourceOfMountedPath(abc.ABC):
  @abc.abstractmethod
  def get_mounted_paths(self, mount_point) -> dict[ParentMount, MountNode]:
      pass


@dataclass
class MountedSecret(SourceOfMountedPath):
  data: dict[str, str]

  @classmethod
  def from_template(cls, template):
    assert template["kind"] == "Secret"
    return cls(data=template["data"])

  def get_mounted_paths(self, mount_point) -> dict[ParentMount, MountNode]:
    return {ParentMount(mount_point): MountNode(k, b64decode(v).decode("utf-8")) for k, v in self.data.items()}


@dataclass
class MountedConfigMap(SourceOfMountedPath):
  data: dict[str, str] = field(default_factory=dict)

  @classmethod
  def from_template(cls, template):
    assert template["kind"] == "ConfigMap"
    return cls(data=template["data"])

  def get_mounted_paths(self, mount_point) -> dict[ParentMount, MountNode]:
    return {ParentMount(mount_point): MountNode(k, v) for k, v in self.data.items()}


@dataclass
class MountedRenderedConfigEmptyDir(SourceOfMountedPath):
  render_config_outputs: list[str] = field(default_factory=list)

  @classmethod
  def from_workload_spec(cls, workload_spec):
    for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
      if "render-config" in container_spec["name"]:
        args = container_spec.get("args") or container_spec["command"][1:]
        for idx, cmd in enumerate(args):
            if cmd == "-output":
                cls.render_config_outputs.append(args[idx + 1].split("/")[-1])

  def get_mounted_paths(self, mount_point) -> dict[ParentMount, MountNode]:
    # Mount node data is empty in tests as it is generated at runtime
    return {ParentMount(mount_point): MountNode(o, "") for o in self.render_config_outputs}


# This is something consuming paths that should through mount points
@dataclass()
class PathConsumer(abc.ABC):
  # Look in the consumer configuration and return strings that look like a ParentMount
  @abc.abstractmethod
  def get_parent_mount_lookalikes(self, deployable_details: DeployableDetails, parent_mount: ParentMount) -> list[str]:
      pass


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


class ContainerSpecPathConsumer(PathConsumer):
  env: dict[str, str] = field(default_factory=dict)
  args: list[str] = field(default_factory=list)

  @classmethod
  def from_container_spec(cls, container_spec):
    return cls(env_values={e["name"]: e["value"] for e in container_spec.get("env", [])},
              args=container_spec.get("command", []) + container_spec.get("args", []))

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



# A configuration consumer has a list of sources of mounted paths
# and a list of paths consumers. The test makes sure that those two are consistent
@dataclass
class ConfigurationConsumer:
  name: str
  paths_consumers: list[PathConsumer] = field(default_factory=list)
  sources_of_mounted_paths: list[SourceOfMountedPath] = field(default_factory=list)

  @classmethod
  def from_workload_spec(cls, name, workload_spec, weight, deployable_details, templates, other_secrets, other_configmaps):
    cls.name = name
    for container_spec in workload_spec["containers"] + workload_spec["initContainers"]:
        # Gather all containers and initContainers from the template spec
        containers = workload_spec["template"]["spec"].get("containers", []) + workload_spec["template"][
            "spec"
        ].get("initContainers", [])

        for container in containers:
            # Determine which secrets are mounted by this container
            mounted_keys = []
            mount_paths = []

            for volume_mount in container.get("volumeMounts", []):
              # Find the corresponding secret volume that matches the volume mount name
              for v in workload_spec["template"]["spec"].get("volumes", []):
                  if volume_mount["name"] == v["name"]:
                      current_volume = v
                      break
              else:
                raise ValueError(
                    f"No matching volume found for mount path {volume_mount['mountPath']} in "
                    f"[{','.join([v['name'] for v in workload_spec['template']['spec'].get('volumes', [])])}]"
                )
                if "secret" in current_volume:
                    # Extract the paths where this volume's secrets are mounted
                    secret = get_secret(templates, other_secrets, current_volume["secret"]["secretName"])
                    assert_exists_according_to_hook_weight(secret, weight, name)
                    cls.sources_of_mounted_paths.append(MountedSecret.from_template(secret))
                elif "configMap" in current_volume:
                    # Parse config map content
                    configmap = get_configmap(templates, current_volume["configMap"]["name"])
                    assert_exists_according_to_hook_weight(configmap, weight, name)
                    cls.sources_of_mounted_paths.append(MountedConfigMap.from_template(configmap))
                elif "emptyDir" in current_volume and current_volume["name"] == "rendered-config":
                    cls.sources_of_mounted_paths.append(MountedRenderedConfigEmptyDir.from_workload_spec(workload_spec))

            mounted_keys = [parent_path + "/" + node_name
                            for source in cls.sources_of_mounted_paths
                            for parent_path, node_name in source.get_mounted_paths()]
            mount_paths = [parent_path for source in cls.sources_of_mounted_paths
                             for parent_path in source.get_mounted_paths()]

            assert len(mounted_keys) == len(set(mounted_keys)), (
                f"Mounted key paths are not unique in {name}: {mounted_keys}"
            )
            assert len(mount_paths) == len(set(mount_paths)), (
                f"Secrets mount paths are not unique in {name}: {mounted_keys}"
            )

