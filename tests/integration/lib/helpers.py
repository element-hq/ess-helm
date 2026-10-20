# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os
import time

import pyhelm3
from lightkube import AsyncClient
from lightkube.models.core_v1 import (
    Capabilities,
    Container,
    ContainerStateTerminated,
    LocalObjectReference,
    PodSpec,
    SeccompProfile,
    SecurityContext,
)
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.core_v1 import ConfigMap, Endpoints, Namespace, Pod, Secret

from ..artifacts import CertKey
from .utils import async_retry_with_timeout, merge


def namespace(name: str) -> Namespace:
    return Namespace(metadata=ObjectMeta(name=name))


def kubernetes_docker_secret(name: str, namespace: str, docker_config_json: str) -> Secret:
    secret = Secret(
        type="kubernetes.io/dockerconfigjson",
        metadata=ObjectMeta(name=name, namespace=namespace, labels={"app.kubernetes.io/managed-by": "pytest"}),
        stringData={".dockerconfigjson": docker_config_json},
    )
    return secret


def kubernetes_tls_secret(name: str, namespace: str, certificate: CertKey) -> Secret:
    secret = Secret(
        type="kubernetes.io/tls",
        metadata=ObjectMeta(name=name, namespace=namespace, labels={"app.kubernetes.io/managed-by": "pytest"}),
        stringData={
            "tls.crt": certificate.cert_bundle_as_pem(),
            "tls.key": certificate.key_as_pem(),
            "ca.crt": certificate.get_root_ca().cert_as_pem(),
        },
    )
    return secret


async def wait_for_endpoint_ready(name, namespace, kube_client):
    """Wait for the addresses of an Endpoints object to be ready. Return the Endpoints object."""

    async def _endpoint_is_ready():
        endpoint = await kube_client.get(Endpoints, name=name, namespace=namespace)
        assert endpoint.subsets, f"Endpoint {name} has no subsets"
        for subset in endpoint.subsets:
            assert subset.addresses, f"Endpoint {name} has a subset without addresses"
            assert not subset.notReadyAddresses, f"Endpoint {name} has a subset with not ready addresses"
            assert subset.ports, f"Endpoint {name} has a subset without ports"
        return endpoint

    # Give the endpoints up to 90 seconds to become ready
    return await async_retry_with_timeout(_endpoint_is_ready, max_retries=90, delay=1, timeout_seconds=90)


async def deploy_with_values_patch(
    generated_data, helm_client: pyhelm3.Client, values_patch: dict, timeout="600s"
) -> tuple[pyhelm3.ReleaseRevision, pyhelm3.Error | None]:
    # Get the current deployed values to patch them
    revision = await helm_client.get_current_revision(
        generated_data.release_name, namespace=generated_data.ess_namespace
    )
    values = await revision.values()
    values = merge(values, values_patch)
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    error = None
    try:
        revision = await helm_client.install_or_upgrade_release(
            generated_data.release_name,
            chart,
            values,
            namespace=generated_data.ess_namespace,
            timeout=timeout,
            atomic=False,
            wait=True,
        )
    except pyhelm3.errors.Error as e:
        error = e
        revision = await helm_client.get_current_revision(
            generated_data.release_name, namespace=generated_data.ess_namespace
        )
    return revision, error


async def get_deployment_marker(kube_client, generated_data, marker: str):
    # The marker should now show delegated_auth
    configmap = await kube_client.get(
        ConfigMap,
        namespace=generated_data.ess_namespace,
        name=f"{generated_data.release_name}-markers",
    )
    return configmap.data.get(marker)


async def run_pod_with_args(kube_client: AsyncClient, generated_data, image_name, pod_name, args):
    pod_pull_secrets = []
    if os.environ.get("CI") and ("DOCKERHUB_USERNAME" in os.environ) and ("DOCKERHUB_TOKEN" in os.environ):
        pod_pull_secrets = [
            LocalObjectReference(name=f"{generated_data.release_name}-dockerhub"),
        ]
    pod = Pod(
        metadata=ObjectMeta(name=pod_name + "-" + str(int(time.time() * 1000)), namespace=generated_data.ess_namespace),
        spec=PodSpec(
            # The helper fails as soon as the container stops with a non zero exit code.
            # A restart policy would never run, so use "Never" and let the command retry itself.
            restartPolicy="Never",
            imagePullSecrets=pod_pull_secrets,
            containers=[
                Container(
                    name="cmd",
                    image=image_name,
                    args=args,
                    securityContext=SecurityContext(
                        seccompProfile=SeccompProfile(type="RuntimeDefault"),
                        capabilities=Capabilities(drop=["ALL"]),
                        readOnlyRootFilesystem=True,
                        allowPrivilegeEscalation=False,
                        runAsNonRoot=True,
                        runAsUser=3000,
                        runAsGroup=3000,
                    ),
                )
            ],
        ),
    )
    assert pod.metadata
    assert pod.metadata.name
    assert pod.metadata.namespace
    await kube_client.create(pod)

    def _terminated_state(found_pod: Pod) -> ContainerStateTerminated | None:
        if not found_pod.status or not found_pod.status.containerStatuses:
            return None
        container_state = found_pod.status.containerStatuses[0].state
        if container_state is None:
            return None
        return container_state.terminated

    async def _container_terminated():
        found_pod = await kube_client.get(Pod, name=pod.metadata.name, namespace=pod.metadata.namespace)
        terminated_state = _terminated_state(found_pod)
        if terminated_state is None:
            # The container is still starting or running. Try again later.
            raise RuntimeError(f"Pod {pod.metadata.name} command is still running")
        return found_pod, terminated_state

    try:
        found_pod, terminated_state = await async_retry_with_timeout(
            _container_terminated,
            max_retries=60,
            timeout_seconds=60,
            delay=1,
        )
    except TimeoutError as e:
        # The retry loop prints one line per attempt. Keep the status out of that message.
        # Fetch the pod once more so the final error holds the full status.
        found_pod = await kube_client.get(Pod, name=pod.metadata.name, namespace=pod.metadata.namespace)
        terminated_state = _terminated_state(found_pod)
        if terminated_state is None:
            raise RuntimeError(
                f"Pod {pod.metadata.name} command did not terminate in time, status: {found_pod.status}"
            ) from e
        # The container finished after the last attempt. Use its result below.

    log_lines = ""
    async for log_line in kube_client.log(pod.metadata.name, namespace=pod.metadata.namespace, container="cmd"):
        log_lines += log_line

    if terminated_state.reason != "Completed":
        # Keep the failed pod so it can be inspected by hand.
        raise RuntimeError(
            f"Pod {pod.metadata.name} command failed with exit code {terminated_state.exitCode}: "
            f"pod status: {found_pod.status}, logs: {log_lines}"
        )
    await kube_client.delete(Pod, name=pod.metadata.name, namespace=generated_data.ess_namespace)
    return log_lines


async def wait_for_all_deployments_rolled_out(kube_client: AsyncClient, namespace: str):
    timeout = 30
    start_time = time.time()
    now = time.time()
    while start_time + timeout > now:
        now = time.time()
        await asyncio.sleep(0.5)
        async for deployment in kube_client.list(Deployment, namespace=namespace):
            # replicas: Total number of non-terminating pods targeted by this deployment
            # updatedReplicas: Total number of non-terminating pods targeted by this deployment that have
            #                  the desired template spec.
            if not deployment.status or not deployment.status.updatedReplicas or not deployment.status.replicas:
                break
            if deployment.status.updatedReplicas != deployment.status.replicas:
                break

            if not deployment.spec or not deployment.spec.replicas:
                break
            if deployment.spec.replicas != deployment.status.replicas:
                break
        else:
            return
