# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Any


class PropertyType(Enum):
    AdditionalConfig = "additional"
    Enabled = "enabled"
    Env = "extraEnv"
    ExposedServices = "exposedServices"
    HostAliases = "hostAliases"
    Image = "image"
    Ingress = "ingress"
    InitContainers = "extraInitContainers"
    Labels = "labels"
    LivenessProbe = "livenessProbe"
    NodeSelector = "nodeSelector"
    PodSecurityContext = "podSecurityContext"
    Postgres = "postgres"
    Replicas = "replicas"
    ReadinessProbe = "readinessProbe"
    Resources = "resources"
    StartupProbe = "startupProbe"
    ServiceAccount = "serviceAccount"
    ServiceMonitor = "serviceMonitors"
    Storage = "storage"
    Tolerations = "tolerations"
    TopologySpreadConstraints = "topologySpreadConstraints"
    Volumes = "extraVolumes"
    VolumeMounts = "extraVolumeMounts"


@dataclass
class ValuesFilePath:
    write_path: tuple[str, ...] | None
    read_path: tuple[str, ...] | None

    @classmethod
    def not_supported(cls):
        return ValuesFilePath(None, None)

    @classmethod
    def read_write(cls, *path: str):
        return ValuesFilePath(tuple(path), tuple(path))

    @classmethod
    def read_elsewhere(cls, *read_path: str):
        return ValuesFilePath(None, tuple(read_path))

    def with_property_type(self, propertyType: PropertyType):
        return ValuesFilePath(
            self.write_path + (propertyType.value,) if self.write_path is not None else None,
            self.read_path + (propertyType.value,) if self.read_path is not None else None,
        )


# We introduce 4 DataClasses to store details of the deployables this chart manages
# * ComponentDetails - details of a top-level deployable. This includes both the headline
#   components like Synapse, Element Web, etc and components that have their own independent
#   properties at the root of the chart, like HAProxy & Postgres. These latter components might
#   only be deployed if specific other top-level components are enabled however they are able to
#   standalone. The shared components should be marked with `is_shared_component` which lets the
#   manifest test setup know they don't have their own independent values files.
#
# * SubComponentDetails - details of a dependent deployable. These are details of a deployable
#   that belongs to / is only ever deployed as part of a top-level component. For example
#   Synapse's Redis can never be deployed out of the context of Synapse.
#
# * SidecarDetails - details of a dependent container. It runs inside a top-level or sub-
#   component. Various Pod properties can't be controlled by the sidecar, they're controlled
#   by the parent component, however Container properties will be editable and there may be
#   additional manifests
#
# * DeployableDetails - a common base class. All of the interesting properties
#   (has_ingress, etc) we care to use to vary test assertions live here. The distinction between
#   ComonentDetails, SubComponentDetails & SidecarDetails should be reserved for how manifests
#   are owned.


# We need to be able to put this and its subclasses into Sets, which means this must be hashable
# We can't be hashable if we have lists, dicts or anything else that isn't hashable. Dataclasses
# are hashable if we set frozen=true, however we can't do that with anything do with __post_init__
# or even a custom __init__ method without object.__setattr__ hacks. We mark all fields bar name
# as hash=False and do unsafe_hash which should be safe enough. The alternative is custom factory
# methods that do the equivalent of __post_init__
@dataclass(unsafe_hash=True)
class DeployableDetails(abc.ABC):
    name: str = field(hash=True)
    value_file_prefix: str | None = field(default=None, hash=False)
    # The "path" through the values file that properties for this deployable will be rooted at
    # by default. The PropertyType value will then finish off the "path".
    values_file_path: ValuesFilePath = field(default=None, hash=False)  # type: ignore[assignment]
    # Per-PropertyType (ingress, env, etc) overrides for the "path" through the values file
    # that should be used for that specific PropertyType.
    values_file_path_overrides: dict[PropertyType, ValuesFilePath] | None = field(default=None, hash=False)

    has_additional_config: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_db: bool = field(default=False, hash=False)
    has_exposed_services: bool = field(default=False, hash=False)
    has_image: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_ingress: bool = field(default=True, hash=False)
    has_automount_service_account_token: bool = field(default=False, hash=False)
    has_workloads: bool = field(default=True, hash=False)
    has_replicas: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_service_monitor: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_storage: bool = field(default=False, hash=False)
    makes_outbound_requests: bool = field(default=None, hash=False)  # type: ignore[assignment]
    is_hook: bool = field(default=False, hash=False)
    has_mount_context: bool = field(default=None, hash=False)  # type: ignore[assignment]
    is_synapse_process: bool = field(default=False, hash=False)

    # Use this to skip mounts point we expect not to be referenced in commands, configs, etc
    # The format is expected to be `container_name: <list of mounts to ignore>`
    ignore_unreferenced_mounts: dict[str, tuple[str, ...]] = field(default_factory=dict, hash=False)
    # Use this to ignore paths found in configuration which do not match an actual mount point
    # The format is expected to be `container_name: <list of paths to ignore>`
    ignore_paths_mismatches: dict[str, tuple[str, ...]] = field(default_factory=dict, hash=False)
    # Use this to skip any configuration consistency checks for given filenames
    # For example, haproxy.cfg has dozens of HTTP Paths but they are not filepaths
    # Instead of noqa-ing all the paths found, we skip the whole file
    skip_path_consistency_for_files: tuple[str, ...] = field(default=(), hash=False)
    # Use this property to add files that we know to be present in PVC/EmptyDirs
    # even if they're not being created by the chart templates
    content_volumes_mapping: dict[str, tuple[str, ...]] = field(default_factory=dict, hash=False)

    def __post_init__(self):
        if self.values_file_path is None:
            self.values_file_path = ValuesFilePath.read_write(self.name)
        if self.has_additional_config is None:
            self.has_additional_config = self.has_workloads
        if self.has_image is None:
            self.has_image = self.has_workloads
        if self.has_service_monitor is None:
            self.has_service_monitor = self.has_workloads
        if self.has_replicas is None:
            self.has_replicas = self.has_workloads
        if self.makes_outbound_requests is None:
            self.makes_outbound_requests = self.has_workloads
        if self.has_mount_context is None:
            self.has_mount_context = self.is_hook

    def _get_values_file_path(self, propertyType: PropertyType) -> ValuesFilePath:
        """
        Returns the "path" through the values file to a given PropertyType.

        The path may exist for both reading and writing, writing only or not at all, but that's
        all encapsulated in ValuesFilePath
        """
        if self.values_file_path_overrides is not None and propertyType in self.values_file_path_overrides:
            return self.values_file_path_overrides[propertyType]
        else:
            return self.values_file_path.with_property_type(propertyType)

    def get_helm_values(
        self, values: dict[str, Any], propertyType: PropertyType, default_value: Any = None
    ) -> dict[str, Any] | None:
        """
        Returns the configured values for this deployable for a given PropertyType.

        The function knows the correct location in the values for this PropertyType for this deployable.

        Returns:
        * None if this deployable explicitly can't configure this PropertyType.
        * The value or empty dict if this PropertyType can be configured.
        """
        values_file_path = self._get_values_file_path(propertyType)
        if values_file_path.read_path is None:
            return None

        values_fragment = values
        for index, helm_key in enumerate(values_file_path.read_path):
            # The last iteration through is the specific property we want to get. We know everything
            # higher this will be a dict, but at the end, for a specific property, we could be
            # trying to fetch an object, an array or a scalar and the default value should reflect that
            if (index + 1) == len(values_file_path.read_path):
                if default_value is None:
                    default_value = {}
                values_fragment = values_fragment.setdefault(helm_key, default_value)
            else:
                values_fragment = values_fragment.setdefault(helm_key, {})
        return values_fragment

    def set_helm_values(self, values: dict[str, Any], propertyType: PropertyType, values_to_set: Any):
        """
        Sets a fragment of values for this deployable for a given PropertyType.
        This fragment can be:
        * A dictionary, in which case it will be merged on top of any values already set.
        * A list, in which case it will be appended on top of any values already set.
        * A scalar that could be in the same, in which case it will replace any value already set.

        The function knows the correct location in the values for this PropertyType for this deployable.
        If this PropertyType can't be set for this deployable then the function silently returns. This
        is to support the case where sub-components/sidecars obtain values from their parent and so
        can't set those PropertyTypes themselves.
        """
        values_file_path = self._get_values_file_path(propertyType)
        if values_file_path.write_path is None:
            return

        values_fragment = values
        for index, helm_key in enumerate(values_file_path.write_path):
            # The last iteration through is the specific property we want to set. We know everything
            # higher this will be a dict, but at the end, for a specific property, we could be
            # trying to set an object, an array or even a scalar
            if (index + 1) == len(values_file_path.write_path):
                if isinstance(values_to_set, dict):
                    values_fragment.setdefault(propertyType.value, {}).update(values_to_set)
                elif isinstance(values_to_set, list):
                    values_fragment.setdefault(propertyType.value, []).extend(values_to_set)
                else:
                    values_fragment[propertyType.value] = values_to_set
            else:
                values_fragment = values_fragment.setdefault(helm_key, {})

    @abc.abstractmethod
    def owns_manifest_named(self, manifest_name: str) -> bool:
        pass

    @abc.abstractmethod
    def deployable_details_for_container(self, container_name: str) -> "DeployableDetails | None":
        pass


@dataclass(unsafe_hash=True)
class SidecarDetails(DeployableDetails):
    # We have to be a workload as we're a sidecar
    has_workloads: bool = True

    parent: DeployableDetails = field(default=None, init=False, hash=False)  # type: ignore[assignment]

    def __post_init__(self):
        super().__post_init__()

        sidecar_values_file_path_overrides = {
            # Not possible, will come from the parent component
            PropertyType.InitContainers: ValuesFilePath.not_supported(),
            PropertyType.NodeSelector: ValuesFilePath.not_supported(),
            PropertyType.PodSecurityContext: ValuesFilePath.not_supported(),
            PropertyType.ServiceAccount: ValuesFilePath.not_supported(),
            PropertyType.Tolerations: ValuesFilePath.not_supported(),
            PropertyType.TopologySpreadConstraints: ValuesFilePath.not_supported(),
            PropertyType.Volumes: ValuesFilePath.not_supported(),
        }
        if self.values_file_path_overrides is None:
            self.values_file_path_overrides = {}
        self.values_file_path_overrides |= sidecar_values_file_path_overrides

        # We dont support replicas
        self.has_replicas = False

    def create_ownership_link(self, parent: "ComponentDetails | SubComponentDetails"):
        self.parent = parent

        # If the sidecar makes outbound requests, the parent will need hostAlias support
        # even if it itself doesn't make outbound requests
        if self.makes_outbound_requests:
            self.parent.makes_outbound_requests = True
            # As we won't have the properties ourselves
            self.makes_outbound_requests = False

    def owns_manifest_named(self, manifest_name: str) -> bool:
        # Sidecars shouldn't own anything that their parent could possibly own
        if self.parent.owns_manifest_named(manifest_name):
            return False

        return manifest_name.startswith(self.name)

    def deployable_details_for_container(self, container_name: str) -> DeployableDetails | None:
        return self if container_name.startswith(self.name) else None


@dataclass(unsafe_hash=True)
class SubComponentDetails(DeployableDetails):
    sidecars: tuple[SidecarDetails, ...] = field(default=(), hash=False)

    def __post_init__(self):
        super().__post_init__()

        for sidecar in self.sidecars:
            sidecar.create_ownership_link(self)

    def owns_manifest_named(self, manifest_name: str) -> bool:
        return manifest_name.startswith(self.name)

    def deployable_details_for_container(self, container_name: str) -> DeployableDetails:
        for sidecar in self.sidecars:
            if sidecar.deployable_details_for_container(container_name) is not None:
                return sidecar
        return self


@dataclass(unsafe_hash=True)
class ComponentDetails(DeployableDetails):
    sub_components: tuple[SubComponentDetails, ...] = field(default=(), hash=False)
    sidecars: tuple[SidecarDetails, ...] = field(default=(), hash=False)

    values_files: tuple[str, ...] = field(init=False, hash=False)
    secret_values_files: tuple[str, ...] = field(init=False, hash=False)

    # Not available after construction
    is_shared_component: InitVar[bool] = field(default=False, hash=False)
    has_credentials: InitVar[bool] = field(default=True, hash=False)
    additional_values_files: InitVar[tuple[str, ...]] = field(default=(), hash=False)
    additional_secret_values_files: InitVar[tuple[str, ...]] = field(default=(), hash=False)

    def __post_init__(
        self,
        is_shared_component: bool,
        has_credentials: bool,
        additional_values_files: tuple[str, ...],
        additional_secret_values_files: tuple[str, ...],
    ):
        super().__post_init__()

        for sidecar in self.sidecars:
            sidecar.create_ownership_link(self)

        if not self.value_file_prefix:
            self.value_file_prefix = self.name
        # Shared components don't have a <component>-minimal-values.yaml
        if is_shared_component:
            self.values_files = ()
            self.secret_values_files = ()
            return

        self.values_files = tuple([f"{self.value_file_prefix}-minimal-values.yaml"] + list(additional_values_files))

        secret_values_files = list(additional_secret_values_files)
        if has_credentials:
            secret_values_files += [
                f"{self.value_file_prefix}-secrets-in-helm-values.yaml",
                f"{self.value_file_prefix}-secrets-externally-values.yaml",
            ]
        if self.has_db:
            secret_values_files += [
                f"{self.value_file_prefix}-postgres-secrets-in-helm-values.yaml",
                f"{self.value_file_prefix}-postgres-secrets-externally-values.yaml",
            ]
        self.secret_values_files = tuple(secret_values_files)

    def owns_manifest_named(self, manifest_name: str) -> bool:
        # We look at sub-components first as while they could have totally distinct names
        # from their parent component, they could have have specific suffixes. If a
        # sub-component owns this manifest it will claim it itself and the top-level
        # component here doesn't own it.
        for sub_component in self.sub_components:
            if sub_component.owns_manifest_named(manifest_name):
                return False

        return manifest_name.startswith(self.name)

    def deployable_details_for_container(self, container_name: str) -> DeployableDetails:
        for sidecar in self.sidecars:
            if sidecar.deployable_details_for_container(container_name) is not None:
                return sidecar
        return self


def make_synapse_worker_sub_component(worker_name: str, worker_type: str) -> SubComponentDetails:
    values_file_path_overrides: dict[PropertyType, ValuesFilePath] = {
        PropertyType.AdditionalConfig: ValuesFilePath.read_elsewhere("synapse", "additional"),
        PropertyType.Env: ValuesFilePath.read_elsewhere("synapse", "extraEnv"),
        PropertyType.HostAliases: ValuesFilePath.read_elsewhere("synapse", "hostAliases"),
        PropertyType.Image: ValuesFilePath.read_elsewhere("synapse", "image"),
        PropertyType.InitContainers: ValuesFilePath.read_elsewhere("synapse", "extraInitContainers"),
        PropertyType.Labels: ValuesFilePath.read_elsewhere("synapse", "labels"),
        PropertyType.NodeSelector: ValuesFilePath.read_elsewhere("synapse", "nodeSelector"),
        PropertyType.PodSecurityContext: ValuesFilePath.read_elsewhere("synapse", "podSecurityContext"),
        PropertyType.ServiceAccount: ValuesFilePath.read_elsewhere("synapse", "serviceAccount"),
        PropertyType.ServiceMonitor: ValuesFilePath.read_elsewhere("synapse", "serviceMonitor"),
        PropertyType.Tolerations: ValuesFilePath.read_elsewhere("synapse", "tolerations"),
        PropertyType.TopologySpreadConstraints: ValuesFilePath.read_elsewhere("synapse", "topologySpreadConstraints"),
        PropertyType.Volumes: ValuesFilePath.read_elsewhere("synapse", "extraVolumes"),
        PropertyType.VolumeMounts: ValuesFilePath.read_elsewhere("synapse", "extraVolumeMounts"),
    }

    return SubComponentDetails(
        f"synapse-{worker_name}",
        values_file_path=ValuesFilePath.read_write("synapse", "workers", worker_name),
        values_file_path_overrides=values_file_path_overrides,
        has_ingress=False,
        is_synapse_process=True,
        has_replicas=(worker_type == "scalable"),
        ignore_unreferenced_mounts={"synapse": ("/tmp",)},
        has_mount_context=True,
        content_volumes_mapping={
            "/media": ("media_store",),
        },
    )


synapse_workers_details = tuple(
    make_synapse_worker_sub_component(worker_name, worker_type)
    for worker_name, worker_type in {
        "account-data": "single",
        "appservice": "single",
        "background": "single",
        "client-reader": "scalable",
        "device-lists": "scalable",
        "encryption": "single",
        "event-creator": "scalable",
        "event-persister": "scalable",
        "federation-inbound": "scalable",
        "federation-reader": "scalable",
        "federation-sender": "scalable",
        "initial-synchrotron": "scalable",
        "media-repository": "single",
        "presence-writer": "single",
        "push-rules": "single",
        "pusher": "scalable",
        "receipts": "scalable",
        "sliding-sync": "scalable",
        "sso-login": "single",
        "synchrotron": "scalable",
        "typing-persister": "single",
        "user-dir": "single",
    }.items()
)


all_components_details = [
    ComponentDetails(
        name="deployment-markers",
        values_file_path=ValuesFilePath.read_write("deploymentMarkers"),
        values_file_path_overrides={
            # Job so no livenessProbe
            PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
            # Job so no readinessProbe
            PropertyType.ReadinessProbe: ValuesFilePath.not_supported(),
            # Job so no startupProbe
            PropertyType.StartupProbe: ValuesFilePath.not_supported(),
        },
        has_additional_config=False,
        has_credentials=False,
        has_image=False,
        has_ingress=False,
        has_automount_service_account_token=True,
        has_replicas=False,
        has_service_monitor=False,
        makes_outbound_requests=False,
        is_hook=True,
        has_mount_context=False,
        is_shared_component=True,
    ),
    ComponentDetails(
        name="init-secrets",
        values_file_path=ValuesFilePath.read_write("initSecrets"),
        values_file_path_overrides={
            # Job so no livenessProbe
            PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
            # Job so no readinessProbe
            PropertyType.ReadinessProbe: ValuesFilePath.not_supported(),
            # Job so no startupProbe
            PropertyType.StartupProbe: ValuesFilePath.not_supported(),
        },
        has_additional_config=False,
        has_image=False,
        has_ingress=False,
        has_automount_service_account_token=True,
        has_replicas=False,
        has_service_monitor=False,
        makes_outbound_requests=False,
        is_hook=True,
        has_mount_context=False,
        is_shared_component=True,
    ),
    ComponentDetails(
        name="haproxy",
        has_additional_config=False,
        has_credentials=False,
        has_ingress=False,
        is_shared_component=True,
        makes_outbound_requests=False,
        ignore_unreferenced_mounts={
            "haproxy": ("/usr/local/etc/haproxy/placeholder",),
        },
        skip_path_consistency_for_files=("haproxy.cfg", "429.http", "path_map_file", "path_map_file_get"),
    ),
    ComponentDetails(
        name="postgres",
        has_additional_config=False,
        has_ingress=False,
        has_storage=True,
        has_replicas=False,
        sidecars=(
            SidecarDetails(
                name="postgres-exporter",
                values_file_path=ValuesFilePath.read_write("postgres", "postgresExporter"),
                values_file_path_overrides={
                    # No manifests of its own, so no labels to set
                    PropertyType.Labels: ValuesFilePath.not_supported(),
                },
                has_additional_config=False,
                has_ingress=False,
                has_service_monitor=False,
                makes_outbound_requests=False,
            ),
        ),
        is_shared_component=True,
        makes_outbound_requests=False,
        content_volumes_mapping={
            "/var/lib/postgres/data": ("pgdata",),
        },
        ignore_unreferenced_mounts={
            "postgres": (
                "/tmp",
                "/var/run/postgresql",
            )
        },
    ),
    ComponentDetails(
        name="redis",
        values_file_path=ValuesFilePath.read_write("redis"),
        is_shared_component=True,
        has_additional_config=False,
        has_ingress=False,
        has_service_monitor=False,
        has_replicas=False,
        makes_outbound_requests=False,
    ),
    ComponentDetails(
        name="matrix-rtc",
        values_file_path=ValuesFilePath.read_write("matrixRTC"),
        has_additional_config=False,
        has_service_monitor=False,
        sub_components=(
            SubComponentDetails(
                name="matrix-rtc-sfu",
                values_file_path=ValuesFilePath.read_write("matrixRTC", "sfu"),
                has_exposed_services=True,
                has_ingress=False,
                has_replicas=False,
                makes_outbound_requests=False,
            ),
        ),
        additional_secret_values_files=(
            "matrix-rtc-external-livekit-secrets-in-helm-values.yaml",
            "matrix-rtc-external-livekit-secrets-externally-values.yaml",
        ),
    ),
    ComponentDetails(
        name="element-admin",
        values_file_path=ValuesFilePath.read_write("elementAdmin"),
        has_additional_config=False,
        has_credentials=False,
        has_service_monitor=False,
        makes_outbound_requests=False,
        ignore_unreferenced_mounts={
            "element-admin": ("/tmp",),
        },
    ),
    ComponentDetails(
        name="element-web",
        values_file_path=ValuesFilePath.read_write("elementWeb"),
        has_credentials=False,
        has_service_monitor=False,
        makes_outbound_requests=False,
        ignore_paths_mismatches={
            "element-web": (
                # Various paths / path prefixes in the nginx config for adjusting headers.
                # Files provided by the base image
                "/50x.html",
                "/config",
                "/health",
                "/index.html",
                "/modules",
                "/version",
                "/non-existant-so-that-this-works-with-read-only-root-filesystem",
            )
        },
        ignore_unreferenced_mounts={
            "element-web": (
                # Explicitly mounted but wildcard included by the base-image
                "/etc/nginx/conf.d/default.conf",
                "/etc/nginx/conf.d/http_customisations.conf",
            )
        },
        content_volumes_mapping={"/tmp": ("element-web-config",)},
    ),
    ComponentDetails(
        name="hookshot",
        has_storage=True,
        has_replicas=False,
        values_file_path_overrides={
            PropertyType.Storage: ValuesFilePath.read_write("hookshot", "storage"),
        },
        values_file_path=ValuesFilePath.read_write("hookshot"),
        ignore_paths_mismatches={
            "hookshot": ("/bin/matrix-hookshot/App/BridgeApp.js",),
        },
        additional_values_files=("hookshot-encryption-enabled-values.yaml",),
    ),
    ComponentDetails(
        name="matrix-authentication-service",
        values_file_path=ValuesFilePath.read_write("matrixAuthenticationService"),
        has_db=True,
        sub_components=(
            SubComponentDetails(
                name="syn2mas",
                values_file_path=ValuesFilePath.read_write("matrixAuthenticationService", "syn2mas"),
                ignore_unreferenced_mounts={
                    "syn2mas-migrate": (
                        # Those are internal to the syn2mas subcommand
                        "/tmp-mas-cli",
                        "/tmp-mas-cli/mas-cli",
                    ),
                },
                ignore_paths_mismatches={
                    # We do not parse the cp bash command
                    "copy-mas-cli": ("/usr/local/bin/mas-cli",),
                    # syn2mas has the homeserver.yaml which contains the media store path
                    # it is actually not mounted in syn2mas
                    "syn2mas-check": (
                        "/as/0/bridge_registration.yaml",
                        "/media/media_store",
                    ),
                    "syn2mas-migrate": (
                        "/as/0/bridge_registration.yaml",
                        "/media/media_store",
                    ),
                },
                content_volumes_mapping={"/tmp-mas-cli": ("mas-cli",)},
                values_file_path_overrides={
                    PropertyType.AdditionalConfig: ValuesFilePath.read_elsewhere(
                        "matrixAuthenticationService", "additional"
                    ),
                    # Job so no livenessProbe
                    PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
                    # Job so no readinessProbe
                    PropertyType.ReadinessProbe: ValuesFilePath.not_supported(),
                    # Job so no startupProbe
                    PropertyType.StartupProbe: ValuesFilePath.not_supported(),
                },
                has_ingress=False,
                has_automount_service_account_token=True,
                has_replicas=False,
                has_service_monitor=False,
                is_hook=True,
                has_mount_context=False,
                makes_outbound_requests=False,
            ),
        ),
    ),
    ComponentDetails(
        name="synapse",
        values_file_path_overrides={
            PropertyType.Storage: ValuesFilePath.read_write("synapse", "media", "storage"),
        },
        has_db=True,
        has_storage=True,
        has_replicas=False,
        is_synapse_process=True,
        additional_values_files=("synapse-worker-example-values.yaml",),
        skip_path_consistency_for_files=("path_map_file", "path_map_file_get"),
        ignore_unreferenced_mounts={"synapse": ("/tmp",)},
        has_mount_context=True,
        content_volumes_mapping={
            "/media": ("media_store",),
        },
        sub_components=synapse_workers_details
        + (
            SubComponentDetails(
                name="synapse-check-config",
                values_file_path=ValuesFilePath.read_write("synapse", "checkConfigHook"),
                values_file_path_overrides={
                    PropertyType.AdditionalConfig: ValuesFilePath.read_elsewhere("synapse", "additional"),
                    PropertyType.Env: ValuesFilePath.read_elsewhere("synapse", "extraEnv"),
                    PropertyType.Image: ValuesFilePath.read_elsewhere("synapse", "image"),
                    PropertyType.InitContainers: ValuesFilePath.read_elsewhere("synapse", "extraInitContainers"),
                    # Job so no livenessProbe
                    PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
                    PropertyType.NodeSelector: ValuesFilePath.read_elsewhere("synapse", "nodeSelector"),
                    PropertyType.PodSecurityContext: ValuesFilePath.read_elsewhere("synapse", "podSecurityContext"),
                    PropertyType.Resources: ValuesFilePath.read_elsewhere("synapse", "resources"),
                    # Job so no readinessProbe
                    PropertyType.ReadinessProbe: ValuesFilePath.not_supported(),
                    PropertyType.ServiceMonitor: ValuesFilePath.read_elsewhere("synapse", "serviceMonitor"),
                    # Job so no startupProbe
                    PropertyType.StartupProbe: ValuesFilePath.not_supported(),
                    PropertyType.Tolerations: ValuesFilePath.read_elsewhere("synapse", "tolerations"),
                    PropertyType.TopologySpreadConstraints: ValuesFilePath.read_elsewhere(
                        "synapse", "topologySpreadConstraints"
                    ),
                    PropertyType.Volumes: ValuesFilePath.read_elsewhere("synapse", "extraVolumes"),
                    PropertyType.VolumeMounts: ValuesFilePath.read_elsewhere("synapse", "extraVolumeMounts"),
                },
                has_ingress=False,
                has_service_monitor=False,
                has_replicas=False,
                is_hook=True,
                makes_outbound_requests=False,
                ignore_unreferenced_mounts={"synapse": ("/tmp",)},
                content_volumes_mapping={
                    "/media": ("media_store",),
                },
            ),
        ),
    ),
    ComponentDetails(
        name="well-known",
        values_file_path=ValuesFilePath.read_write("wellKnownDelegation"),
        has_additional_config=True,
        has_credentials=False,
        has_workloads=False,
    ),
]


def _get_all_deployables_details() -> set[DeployableDetails]:
    deployables_details = set[DeployableDetails]()
    for deployable_details in all_components_details:
        deployables_details.add(deployable_details)
        deployables_details.update(deployable_details.sub_components)
        for sub_component in deployable_details.sub_components:
            deployables_details.update(sub_component.sidecars)
        deployables_details.update(deployable_details.sidecars)
    return deployables_details


all_deployables_details = _get_all_deployables_details()


_extra_values_files_to_test: list[str] = [
    "example-default-enabled-components-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-externally-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-migrate-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-migrate-secrets-externally-values.yaml",
    "matrix-rtc-host-mode-values.yaml",
]

_extra_secret_values_files_to_test = [
    "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-dry-run-secrets-externally-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-migrate-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-syn2mas-migrate-secrets-externally-values.yaml",
]

_extra_services_values_files_to_test = [
    "matrix-rtc-exposed-services-tls-values.yaml",
    "matrix-rtc-exposed-services-cert-manager-values.yaml",
]

secret_values_files_to_test = set(
    sum([component_details.secret_values_files for component_details in all_components_details], tuple())
) | set(_extra_secret_values_files_to_test)

values_files_to_test = (
    set(sum([component_details.values_files for component_details in all_components_details], tuple()))
    | set(_extra_values_files_to_test)
    | set(_extra_services_values_files_to_test)
)

services_values_files_to_test = set(_extra_services_values_files_to_test)
