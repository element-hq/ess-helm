# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import abc
from dataclasses import InitVar, dataclass, field
from typing import Any, Callable, Self

# We introduce 3 DataClasses to store details of the deployables this chart manages
# * ComponentDetails - details of a top-level deployable. This includes both the headlines
#   components like Synapse, Element Web, etc and components that have their own independent
#   properties at the root of the chart, like HAProxy & Postgres. These latter components might
#   only be deployed if specific other top-level components are enabled however they are able to
#   standalone. The shared components should be marked with `is_shared_component` which lets the
#   manifest test setup know they don't have their own independent values files
#
# * SubComponentDetails - details of a dependent deployable. These are details of a deployable
#   that belongs to / is only ever deployed as part of a top-level component. For example
#   Synapse's Redis can never be deployed out of the context of Synapse.
#
# * DeployableDetails - a common base class for ComponentDetails and SubComponentDetails. All
#   of the interesting properties (has_ingress, etc) we care to use to vary test assertions live
#   here. The distinction between ComonentDetails and SubComponent details should be reserved for
#   how the values files need to be manipulated.


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
    helm_key: str = field(default=None, hash=False)  # type: ignore[assignment]

    has_db: bool = field(default=False, hash=False)  # type: ignore[assignment]
    has_image: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_extra_env: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_ingress: bool = field(default=True, hash=False)
    has_workloads: bool = field(default=True, hash=False)
    has_service_monitor: bool = field(default=None, hash=False)  # type: ignore[assignment]
    has_storage: bool = field(default=False, hash=False)
    has_topology_spread_constraints: bool = field(default=None, hash=False)  # type: ignore[assignment]

    paths_consistency_noqa: tuple[str, ...] = field(default=(), hash=False)
    skip_path_consistency_for_files: tuple[str, ...] = field(default=(), hash=False)

    def __post_init__(self):
        if self.helm_key is None:
            self.helm_key = self.name
        if self.has_image is None:
            self.has_image = self.has_workloads
        if self.has_extra_env is None:
            self.has_extra_env = self.has_workloads
        if self.has_service_monitor is None:
            self.has_service_monitor = self.has_workloads
        if self.has_topology_spread_constraints is None:
            self.has_topology_spread_constraints = self.has_workloads

    @abc.abstractmethod
    def get_helm_values_fragment(self, values: dict[str, Any]) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def owns_manifest_named(seflf, manifest_name: str) -> bool:
        pass

    @abc.abstractmethod
    def should_visit_with_values(
        self, if_condition: Callable[[Self], bool], ignore_uses_parent_properties: bool = False
    ):
        pass


@dataclass(unsafe_hash=True)
class SubComponentDetails(DeployableDetails):
    uses_parent_properties: bool = field(default=False, hash=False)
    parent_helm_key: str = field(default=None, hash=False)  # type: ignore[assignment]

    def get_helm_values_fragment(self, values: dict[str, Any]) -> dict[str, Any]:
        return values.setdefault(self.parent_helm_key, {}).setdefault(self.helm_key, {})

    def owns_manifest_named(self, manifest_name: str) -> bool:
        return manifest_name.startswith(self.name)

    def should_visit_with_values(
        self, if_condition: Callable[[Self], bool], ignore_uses_parent_properties: bool = False
    ):
        return (ignore_uses_parent_properties or not self.uses_parent_properties) and if_condition(self)


@dataclass(unsafe_hash=True)
class ComponentDetails(DeployableDetails):
    sub_components: tuple[SubComponentDetails, ...] = field(default=(), hash=False)

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

        for sub_component in self.sub_components:
            sub_component.parent_helm_key = self.helm_key

    def get_helm_values_fragment(self, values: dict[str, Any]) -> dict[str, Any]:
        return values.setdefault(self.helm_key, {})

    def owns_manifest_named(self, manifest_name: str) -> bool:
        # We look at sub-components first as while they could have totally distinct names
        # from their parent component, they could have have specific suffixes. If a
        # sub-component owns this manifest it will claim it itself and the top-level
        # component here doesn't own it.
        for sub_component in self.sub_components:
            if sub_component.owns_manifest_named(manifest_name):
                return False

        return manifest_name.startswith(self.name)

    def should_visit_with_values(
        self, if_condition: Callable[[Self], bool], ignore_uses_parent_properties: bool = False
    ):
        return if_condition(self)


all_components_details = [
    ComponentDetails(
        name="init-secrets",
        helm_key="initSecrets",
        has_image=False,
        has_ingress=False,
        has_extra_env=False,
        has_service_monitor=False,
        has_topology_spread_constraints=False,
        is_shared_component=True,
    ),
    ComponentDetails(
        name="haproxy",
        has_ingress=False,
        has_extra_env=False,
        is_shared_component=True,
        skip_path_consistency_for_files=("haproxy.cfg", "429.http", "failover_map_file", "path_map_file", "path_map_file_get"),
    ),
    ComponentDetails(
        name="postgres",
        has_ingress=False,
        has_extra_env=False,
        has_storage=True,
        paths_consistency_noqa=("/docker-entrypoint-initdb.d/init-ess-dbs.sh",),
        is_shared_component=True,
    ),
    ComponentDetails(
        name="matrix-rtc",
        helm_key="matrixRTC",
        has_topology_spread_constraints=False,
        sub_components=(
            SubComponentDetails(
                name="matrix-rtc-sfu", helm_key="sfu", has_topology_spread_constraints=False, has_ingress=False
            ),
        ),
        shared_component_names=("init-secrets",),
    ),
    ComponentDetails(
        name="element-web",
        helm_key="elementWeb",
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
        helm_key="matrixAuthenticationService",
        has_db=True,
        shared_component_names=("init-secrets", "postgres"),
    ),
    ComponentDetails(
        name="synapse",
        has_db=True,
        has_storage=True,
        additional_values_files=("synapse-worker-example-values.yaml",),
        skip_path_consistency_for_files=("path_map_file", "path_map_file_get"),
        sub_components=(
            SubComponentDetails(
                name="synapse-redis",
                helm_key="redis",
                has_ingress=False,
                has_extra_env=False,
                has_service_monitor=False,
                has_topology_spread_constraints=False,
            ),
            SubComponentDetails(
                name="synapse-check-config-hook",
                helm_key="checkConfigHook",
                has_ingress=False,
                has_service_monitor=False,
                uses_parent_properties=True,
            ),
        ),
        shared_component_names=("init-secrets", "haproxy", "postgres"),
    ),
    ComponentDetails(
        name="well-known",
        helm_key="wellKnownDelegation",
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
