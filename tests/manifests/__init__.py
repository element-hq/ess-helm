# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Any


class PropertyType(Enum):
    Env = "extraEnv"
    Image = "image"
    Ingress = "ingress"
    Labels = "labels"
    LivenessProbe = "livenessProbe"
    PodSecurityContext = "podSecurityContext"
    Postgres = "postgres"
    ReadinessProbe = "readinessProbe"
    StartupProbe = "startupProbe"
    ServiceAccount = "serviceAccount"
    ServiceMonitor = "serviceMonitors"
    Tolerations = "tolerations"
    TopologySpreadConstraints = "topologySpreadConstraints"


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
    helm_keys: tuple[str, ...] = field(default=None, hash=False)  # type: ignore[arg-type]
    # Per-PropertyType (ingress, env, etc) overrides for the "path" through the values file
    # that should be used for that specific PropertyType. A path of None for a given PropertyType
    # means this deployable can't set values of that property type. That doesn't mean that the
    # deployable won't have e.g. env vars, it means they will be sourced from their parent.
    helm_keys_overrides: dict[PropertyType, tuple[str, ...] | None] | None = field(default=None, hash=False)

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
        if self.helm_keys is None or len(self.helm_keys) == 0:
            self.helm_keys = (self.name,)
        if self.has_image is None:
            self.has_image = self.has_workloads
        if self.has_service_monitor is None:
            self.has_service_monitor = self.has_workloads
        if self.has_topology_spread_constraints is None:
            self.has_topology_spread_constraints = self.has_workloads

    def _get_helm_keys(self, propertyType: PropertyType) -> tuple[str, ...] | None:
        """
        Returns the "path" (tuple of values keys) to a given PropertyType.

        Returns None if this deployable has an override explicitly set to None to indicated
        that this deployable doesn't have its own values for that PropertyType.
        """
        if (
            propertyType is not None
            and self.helm_keys_overrides is not None
            and propertyType in self.helm_keys_overrides
        ):
            return self.helm_keys_overrides[propertyType]
        else:
            return self.helm_keys + (propertyType.value,)

    def get_helm_values(self, values: dict[str, Any], propertyType: PropertyType) -> dict[str, Any] | None:
        """
        Returns the configured values for this deployable for a given PropertyType.

        The function knows the correct location in the values for this PropertyType for this deployable.

        Returns:
        * None if this deployable explicitly can't configure this PropertyType.
        * The value or empty dict if this PropertyType can be configured.
        """
        helm_keys = self._get_helm_keys(propertyType)
        if helm_keys is None:
            return None

        values_fragment = values
        for helm_key in helm_keys:
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
        helm_keys = self._get_helm_keys(propertyType)
        if helm_keys is None:
            return

        values_fragment = values
        for index, helm_key in enumerate(helm_keys):
            # The last iteration through is the specific property we want to set. We know everything
            # higher this will be a dict, but at the end, for a specific property, we could be
            # trying to set an object, an array or even a scalar
            if (index + 1) == len(helm_keys):
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

        sidecar_helm_keys_overrides = {
            # Not possible, will come from the parent component
            PropertyType.PodSecurityContext: None,
            PropertyType.ServiceAccount: None,
            PropertyType.Tolerations: None,
            PropertyType.TopologySpreadConstraints: None,
        }
        if self.helm_keys_overrides is None:
            self.helm_keys_overrides = {}
        self.helm_keys_overrides |= sidecar_helm_keys_overrides

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

    def __post_init__(
        self,
        is_shared_component: bool,
        shared_component_names: tuple[str, ...],
        additional_values_files: tuple[str, ...],
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

        secret_values_files = []
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


def make_synapse_worker_sub_component(worker_name: str) -> SubComponentDetails:
    helm_keys_overrides: dict[PropertyType, tuple[str, ...] | None] = {
        # Doesn't have its own env, comes from synapse.extraEnv
        PropertyType.Env: None,
        # Doesn't have its own image, comes from synapse.image
        PropertyType.Image: None,
        # Doesn't have its own labels, comes from synapse.labels
        PropertyType.Labels: None,
        # Doesn't have its own podSecurityContext, comes from synapse.podSecurityContext
        PropertyType.PodSecurityContext: None,
        # Doesn't have its own serviceAccount, comes from synapse.serviceAccount
        PropertyType.ServiceAccount: None,
        # Doesn't have its own serviceMonitor, comes from synapse.serviceMonitor
        PropertyType.ServiceMonitor: None,
        # has_workloads and so tolerations but comes from synapse.tolerations
        PropertyType.Tolerations: None,
        # has_topology_spread_constraints and so topologySpreadConstraints
        # but comes from synapse.topologySpreadConstraints
        PropertyType.TopologySpreadConstraints: None,
    }

    return SubComponentDetails(
        f"synapse-{worker_name}",
        helm_keys=("synapse", "workers", worker_name),
        helm_keys_overrides=helm_keys_overrides,
        has_ingress=False,
        is_synapse_process=True,
    )


synapse_workers_details = tuple(
    make_synapse_worker_sub_component(worker_name)
    for worker_name in [
        "appservice",
        "background",
        "client-reader",
        "encryption",
        "event-creator",
        "event-persister",
        "federation-inbound",
        "federation-reader",
        "federation-sender",
        "initial-synchrotron",
        "media-repository",
        "presence-writer",
        "push-rules",
        "pusher",
        "receipts-account",
        "sliding-sync",
        "sso-login",
        "synchrotron",
        "typing-persister",
        "user-dir",
    ]
)


all_components_details = [
    ComponentDetails(
        name="init-secrets",
        helm_keys=("initSecrets",),
        helm_keys_overrides={
            # Job so no livenessProbe
            PropertyType.LivenessProbe: None,
            # Job so no readinessProbe
            PropertyType.ReadinessProbe: None,
            # Job so no startupProbe
            PropertyType.StartupProbe: None,
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
                helm_keys=("postgres", "postgresExporter"),
                helm_keys_overrides={
                    # No manifests of its own, so no labels to set
                    PropertyType.Labels: None,
                },
                has_ingress=False,
                has_service_monitor=False,
            ),
        ),
        paths_consistency_noqa=("/docker-entrypoint-initdb.d/init-ess-dbs.sh",),
        is_shared_component=True,
    ),
    ComponentDetails(
        name="matrix-rtc",
        helm_keys=("matrixRTC",),
        has_topology_spread_constraints=False,
        sub_components=(
            SubComponentDetails(
                name="matrix-rtc-sfu",
                helm_keys=("matrixRTC", "sfu"),
                has_topology_spread_constraints=False,
                has_ingress=False,
            ),
        ),
        shared_component_names=("init-secrets",),
    ),
    ComponentDetails(
        name="element-web",
        helm_keys=("elementWeb",),
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
        helm_keys=("matrixAuthenticationService",),
        has_db=True,
        shared_component_names=("init-secrets", "postgres"),
    ),
    ComponentDetails(
        name="synapse",
        has_db=True,
        has_storage=True,
        is_synapse_process=True,
        additional_values_files=("synapse-worker-example-values.yaml",),
        skip_path_consistency_for_files=("path_map_file", "path_map_file_get"),
        sub_components=synapse_workers_details
        + (
            SubComponentDetails(
                name="synapse-redis",
                helm_keys=("synapse", "redis"),
                has_ingress=False,
                has_service_monitor=False,
                has_topology_spread_constraints=False,
            ),
            SubComponentDetails(
                name="synapse-check-config-hook",
                helm_keys=("synapse", "checkConfigHook"),
                helm_keys_overrides={
                    # has_workloads but comes from synapse.extraEnv
                    PropertyType.Env: None,
                    # has_workloads but comes from synapse.image
                    PropertyType.Image: None,
                    # Job so no livenessProbe
                    PropertyType.LivenessProbe: None,
                    # has_workloads and so podSecurityContext but comes from synapse.podSecurityContext
                    PropertyType.PodSecurityContext: None,
                    # Job so no readinessProbe
                    PropertyType.ReadinessProbe: None,
                    # Job so no startupProbe
                    PropertyType.StartupProbe: None,
                    # has_workloads and so tolerations but comes from synapse.tolerations
                    PropertyType.Tolerations: None,
                    # has_topology_spread_constraints and so topologySpreadConstraints
                    # but comes from synapse.topologySpreadConstraints
                    PropertyType.TopologySpreadConstraints: None,
                },
                has_ingress=False,
                has_service_monitor=False,
            ),
        ),
        shared_component_names=("init-secrets", "haproxy", "postgres"),
    ),
    ComponentDetails(
        name="well-known",
        helm_keys=("wellKnownDelegation",),
        has_workloads=False,
        shared_component_names=("haproxy",),
    ),
]


def _get_deployables_details_from_base_components_names(
    base_components_names: list[str],
) -> tuple[DeployableDetails, ...]:
    component_names_to_details = {
        component_details.name: component_details for component_details in all_components_details
    }
    deployables_details_in_use = set[DeployableDetails]()
    for base_component_name in base_components_names:
        for component_name in component_names_to_details[base_component_name].active_component_names:
            component_details = component_names_to_details[component_name]
            deployables_details_in_use.add(component_details)
            deployables_details_in_use.update(component_details.sub_components)
            deployables_details_in_use.update(component_details.sidecars)
            for sub_component in component_details.sub_components:
                deployables_details_in_use.update(sub_component.sidecars)

    return tuple(deployables_details_in_use)


_single_component_values_files_to_base_components_names: dict[str, list[str]] = {
    values_file: [details.name]
    for details in all_components_details
    for values_file in (details.values_files + details.secret_values_files)
}

_multi_component_values_files_to_base_components_names: dict[str, list[str]] = {
    "example-default-enabled-components-values.yaml": [
        "element-web",
        "matrix-authentication-service",
        "synapse",
        "well-known",
    ],
    "matrix-authentication-service-synapse-secrets-externally-values.yaml": [
        "matrix-authentication-service",
        "synapse",
    ],
    "matrix-authentication-service-keep-auth-in-synapse-values.yaml": [
        "matrix-authentication-service",
        "synapse",
    ],
    "matrix-authentication-service-synapse-secrets-in-helm-values.yaml": ["matrix-authentication-service", "synapse"],
    "matrix-rtc-external-livekit-secrets-in-helm-values.yaml": ["matrix-rtc"],
    "matrix-rtc-external-livekit-secrets-externally-values.yaml": ["matrix-rtc"],
}


values_files_to_deployables_details = {
    values_file: _get_deployables_details_from_base_components_names(base_components_names)
    for values_file, base_components_names in (
        _single_component_values_files_to_base_components_names | _multi_component_values_files_to_base_components_names
    ).items()
}

_extra_secret_values_files_to_test = [
    "matrix-authentication-service-synapse-secrets-in-helm-values.yaml",
    "matrix-authentication-service-synapse-secrets-externally-values.yaml",
    "matrix-rtc-external-livekit-secrets-in-helm-values.yaml",
    "matrix-rtc-external-livekit-secrets-externally-values.yaml",
]
secret_values_files_to_test = [
    values_file for details in all_components_details for values_file in details.secret_values_files
] + _extra_secret_values_files_to_test

values_files_to_test = [
    values_file for values_file in values_files_to_deployables_details if values_file not in secret_values_files_to_test
]
values_files_with_ingresses = [
    values_file
    for values_file, deployables_details in values_files_to_deployables_details.items()
    if any([deployable_details.has_ingress for deployable_details in deployables_details])
    and values_file not in secret_values_files_to_test
]
_extra_services_values_files_to_test = ["matrix-rtc-exposed-services-values.yaml", "matrix-rtc-host-mode-values.yaml"]

services_values_files_to_test = [
    values_file for details in all_components_details for values_file in details.values_files
] + _extra_services_values_files_to_test
