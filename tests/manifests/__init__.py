# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Any


class PropertyType(Enum):
    Enabled = "enabled"
    Env = "extraEnv"
    Image = "image"
    Ingress = "ingress"
    Labels = "labels"
    LivenessProbe = "livenessProbe"
    PodSecurityContext = "podSecurityContext"
    Postgres = "postgres"
    Replicas = "replicas"
    ReadinessProbe = "readinessProbe"
    Resources = "resources"
    StartupProbe = "startupProbe"
    ServiceAccount = "serviceAccount"
    ServiceMonitor = "serviceMonitors"
    Tolerations = "tolerations"
    TopologySpreadConstraints = "topologySpreadConstraints"


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

    has_db: bool = field(default=False, hash=False)
    has_image: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_ingress: bool = field(default=True, hash=False)
    has_workloads: bool = field(default=True, hash=False)
    has_service_monitor: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_storage: bool = field(default=False, hash=False)
    has_topology_spread_constraints: bool = field(default=None, hash=False)  # type: ignore[assignment]
    is_synapse_process: bool = field(default=False)

    paths_consistency_noqa: tuple[str, ...] = field(default=(), hash=False)
    skip_path_consistency_for_files: tuple[str, ...] = field(default=(), hash=False)

    def __post_init__(self):
        if self.values_file_path is None:
            self.values_file_path = ValuesFilePath.read_write(self.name)
        if self.has_image is None:
            self.has_image = self.has_workloads
        if self.has_service_monitor is None:
            self.has_service_monitor = self.has_workloads
        if self.has_topology_spread_constraints is None:
            self.has_topology_spread_constraints = self.has_workloads

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
    parent: DeployableDetails = field(default=None, init=False, hash=False)  # type: ignore[assignment]

    def __post_init__(self):
        super().__post_init__()

        sidecar_values_file_path_overrides = {
            # Not possible, will come from the parent component
            PropertyType.PodSecurityContext: ValuesFilePath.not_supported(),
            PropertyType.ServiceAccount: ValuesFilePath.not_supported(),
            PropertyType.Tolerations: ValuesFilePath.not_supported(),
            PropertyType.TopologySpreadConstraints: ValuesFilePath.not_supported(),
            PropertyType.Replicas: ValuesFilePath.not_supported(),
        }
        if self.values_file_path_overrides is None:
            self.values_file_path_overrides = {}
        self.values_file_path_overrides |= sidecar_values_file_path_overrides

        # Not possible, will come from the parent components
        self.has_topology_spread_constraints = False

        # We have to be a workload as we're a sidecar
        self.has_workloads = True

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
            sidecar.parent = self

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

    active_component_names: tuple[str, ...] = field(init=False, hash=False)
    values_files: tuple[str, ...] = field(init=False, hash=False)
    secret_values_files: tuple[str, ...] = field(init=False, hash=False)

    # Not available after construction
    is_shared_component: InitVar[bool] = field(default=False, hash=False)
    shared_component_names: InitVar[tuple[str, ...]] = field(default=(), hash=False)
    additional_values_files: InitVar[tuple[str, ...]] = field(default=(), hash=False)
    additional_secret_values_files: InitVar[tuple[str, ...]] = field(default=(), hash=False)

    def __post_init__(
        self,
        is_shared_component: bool,
        shared_component_names: tuple[str, ...],
        additional_values_files: tuple[str, ...],
        additional_secret_values_files: tuple[str, ...],
    ):
        super().__post_init__()

        for sidecar in self.sidecars:
            sidecar.parent = self

        if not self.value_file_prefix:
            self.value_file_prefix = self.name
        # Shared components don't have a <component>-minimal-values.yaml
        if is_shared_component:
            self.active_component_names = (self.name,)
            self.values_files = ()
            self.secret_values_files = ()
            return

        assert self.has_db == ("postgres" in shared_component_names)

        self.active_component_names = tuple([self.name] + list(shared_component_names))
        self.values_files = tuple([f"{self.value_file_prefix}-minimal-values.yaml"] + list(additional_values_files))

        secret_values_files = list(additional_secret_values_files)
        if "init-secrets" in shared_component_names:
            secret_values_files += [
                f"{self.value_file_prefix}-secrets-in-helm-values.yaml",
                f"{self.value_file_prefix}-secrets-externally-values.yaml",
            ]
        if "postgres" in shared_component_names:
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
        PropertyType.Env: ValuesFilePath.read_elsewhere("synapse", "extraEnv"),
        PropertyType.Image: ValuesFilePath.read_elsewhere("synapse", "image"),
        PropertyType.Labels: ValuesFilePath.read_elsewhere("synapse", "labels"),
        PropertyType.PodSecurityContext: ValuesFilePath.read_elsewhere("synapse", "podSecurityContext"),
        PropertyType.ServiceAccount: ValuesFilePath.read_elsewhere("synapse", "serviceAccount"),
        PropertyType.ServiceMonitor: ValuesFilePath.read_elsewhere("synapse", "serviceMonitor"),
        PropertyType.Tolerations: ValuesFilePath.read_elsewhere("synapse", "tolerations"),
        PropertyType.TopologySpreadConstraints: ValuesFilePath.read_elsewhere("synapse", "topologySpreadConstraints"),
    }

    if worker_type == "single":
        values_file_path_overrides[PropertyType.Replicas] = ValuesFilePath.not_supported()

    return SubComponentDetails(
        f"synapse-{worker_name}",
        values_file_path=ValuesFilePath.read_write("synapse", "workers", worker_name),
        values_file_path_overrides=values_file_path_overrides,
        has_ingress=False,
        is_synapse_process=True,
    )


synapse_workers_details = tuple(
    make_synapse_worker_sub_component(worker_name, worker_type)
    for worker_name, worker_type in {
        "appservice": "single",
        "background": "single",
        "client-reader": "scalable",
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
        "receipts-account": "single",
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
            # Job so no replicas
            PropertyType.Replicas: ValuesFilePath.not_supported(),
        },
        has_image=False,
        has_ingress=False,
        has_service_monitor=False,
        has_topology_spread_constraints=False,
        is_shared_component=True,
    ),
    ComponentDetails(
        name="init-secrets",
        values_file_path=ValuesFilePath.read_write("initSecrets"),
        values_file_path_overrides={
            # Job so no replicas
            PropertyType.Replicas: ValuesFilePath.not_supported(),
            # Job so no livenessProbe
            PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
            # Job so no readinessProbe
            PropertyType.ReadinessProbe: ValuesFilePath.not_supported(),
            # Job so no startupProbe
            PropertyType.StartupProbe: ValuesFilePath.not_supported(),
        },
        has_image=False,
        has_ingress=False,
        has_service_monitor=False,
        has_topology_spread_constraints=False,
        is_shared_component=True,
    ),
    ComponentDetails(
        name="haproxy",
        has_ingress=False,
        is_shared_component=True,
        skip_path_consistency_for_files=("haproxy.cfg", "429.http", "path_map_file", "path_map_file_get"),
    ),
    ComponentDetails(
        name="postgres",
        has_ingress=False,
        has_storage=True,
        sidecars=(
            SidecarDetails(
                name="postgres-exporter",
                values_file_path=ValuesFilePath.read_write("postgres", "postgresExporter"),
                values_file_path_overrides={
                    # No manifests of its own, so no labels to set
                    PropertyType.Labels: ValuesFilePath.not_supported(),
                },
                has_ingress=False,
                has_service_monitor=False,
            ),
        ),
        values_file_path_overrides={
            # StatefulSet without replicas
            PropertyType.Replicas: ValuesFilePath.not_supported(),
        },
        paths_consistency_noqa=("/docker-entrypoint-initdb.d/init-ess-dbs.sh",),
        is_shared_component=True,
    ),
    ComponentDetails(
        name="matrix-rtc",
        values_file_path=ValuesFilePath.read_write("matrixRTC"),
        has_topology_spread_constraints=False,
        sub_components=(
            SubComponentDetails(
                name="matrix-rtc-sfu",
                values_file_path=ValuesFilePath.read_write("matrixRTC", "sfu"),
                has_topology_spread_constraints=False,
                has_ingress=False,
                values_file_path_overrides={
                    # Deployment which do not support replicas
                    PropertyType.Replicas: ValuesFilePath.not_supported(),
                },
            ),
        ),
        shared_component_names=("init-secrets",),
        additional_secret_values_files=(
            "matrix-rtc-external-livekit-secrets-in-helm-values.yaml",
            "matrix-rtc-external-livekit-secrets-externally-values.yaml",
        ),
    ),
    ComponentDetails(
        name="element-web",
        values_file_path=ValuesFilePath.read_write("elementWeb"),
        has_service_monitor=False,
        paths_consistency_noqa=(
            # Explicitly mounted but wildcard included by the base-image
            "/etc/nginx/conf.d/default.conf",
            "/etc/nginx/conf.d/http_customisations.conf",
            # Env var we set to a deliberately non-existant path
            "/non-existant-so-that-this-works-with-read-only-root-filesystem",
            # Various paths / path prefixes in the nginx config for adjusting headers.
            # Files provided by the base image
            "/50x.html",
            "/config",
            "/health",
            "/index.html",
            "/modules",
            "/version",
        ),
    ),
    ComponentDetails(
        name="matrix-authentication-service",
        values_file_path=ValuesFilePath.read_write("matrixAuthenticationService"),
        has_db=True,
        shared_component_names=("deployment-markers", "init-secrets", "postgres"),
    ),
    ComponentDetails(
        name="synapse",
        has_db=True,
        has_storage=True,
        is_synapse_process=True,
        additional_values_files=("synapse-worker-example-values.yaml",),
        skip_path_consistency_for_files=("path_map_file", "path_map_file_get"),
        values_file_path_overrides={
            # StatefulSet which do not support replicas
            PropertyType.Replicas: ValuesFilePath.not_supported(),
        },
        sub_components=synapse_workers_details
        + (
            SubComponentDetails(
                name="synapse-redis",
                values_file_path=ValuesFilePath.read_write("synapse", "redis"),
                has_ingress=False,
                has_service_monitor=False,
                has_topology_spread_constraints=False,
                values_file_path_overrides={
                    # Deployment which do not support replicas
                    PropertyType.Replicas: ValuesFilePath.not_supported(),
                },
            ),
            SubComponentDetails(
                name="synapse-check-config",
                values_file_path=ValuesFilePath.read_write("synapse", "checkConfigHook"),
                values_file_path_overrides={
                    PropertyType.Env: ValuesFilePath.read_elsewhere("synapse", "extraEnv"),
                    PropertyType.Image: ValuesFilePath.read_elsewhere("synapse", "image"),
                    # Job so no livenessProbe
                    PropertyType.LivenessProbe: ValuesFilePath.not_supported(),
                    PropertyType.PodSecurityContext: ValuesFilePath.read_elsewhere("synapse", "podSecurityContext"),
                    # Job so no replicas
                    PropertyType.Replicas: ValuesFilePath.not_supported(),
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
                },
                has_ingress=False,
                has_service_monitor=False,
            ),
        ),
        shared_component_names=("deployment-markers", "init-secrets", "haproxy", "postgres"),
    ),
    ComponentDetails(
        name="well-known",
        values_file_path=ValuesFilePath.read_write("wellKnownDelegation"),
        has_workloads=False,
        shared_component_names=("haproxy",),
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
    "matrix-authentication-service-keep-auth-in-synapse-values.yaml",
]

_extra_secret_values_files_to_test = [
    "matrix-authentication-service-synapse-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-secrets-externally-values.yaml",
]

_extra_services_values_files_to_test = [
    "matrix-rtc-exposed-services-values.yaml",
    "matrix-rtc-host-mode-values.yaml",
]

secret_values_files_to_test = set(
    sum([component_details.secret_values_files for component_details in all_components_details], tuple())
) | set(_extra_secret_values_files_to_test)

values_files_to_test = set(
    sum([component_details.values_files for component_details in all_components_details], tuple())
) | set(_extra_values_files_to_test)


services_values_files_to_test = values_files_to_test | set(_extra_services_values_files_to_test)
