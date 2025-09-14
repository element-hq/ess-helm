# Copyright 2024-2025 New Vector Ltd
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
    LocalObjectReference,
    PodSpec,
    SeccompProfile,
    SecurityContext,
)
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import ReplicaSet
from lightkube.resources.core_v1 import ConfigMap, Endpoints, Namespace, Pod, Secret

from ..artifacts import CertKey
from .utils import merge


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


async def wait_for_endpoint_ready(name, namespace, cluster, kube_client):
    await asyncio.to_thread(
        cluster.wait,
        name=f"endpoints/{name}",
        namespace=namespace,
        waitfor="jsonpath='{.subsets[].addresses}'",
    )
    # We wait maximum 30 seconds for the endpoints to be ready
    start_time = time.time()
    while time.time() - start_time < 30:
        endpoint = await kube_client.get(Endpoints, name=name, namespace=namespace)

        for subset in endpoint.subsets:
            if not subset or subset.notReadyAddresses or not subset.addresses or not subset.ports:
                await asyncio.sleep(0.1)
                break
        else:
            break
    return endpoint


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
    start_time = time.time()
    now = time.time()
    completed = False
    while start_time + 60 > now and not completed:
        found_pod = await kube_client.get(Pod, name=pod.metadata.name, namespace=pod.metadata.namespace)
        if (
            found_pod.status
            and found_pod.status.containerStatuses
            and found_pod.status.containerStatuses[0].state
            and found_pod.status.containerStatuses[0].state.terminated
            and found_pod.status.containerStatuses[0].state.terminated.reason == "Completed"
        ):
            completed = True
        else:
            now = time.time()
            await asyncio.sleep(1)
    else:
        if start_time + 60 <= now:
            raise RuntimeError(
                f"Pod {pod.metadata.name} did not start in time "
                f"(failed after {now - start_time} seconds), "
                f"pod status: {found_pod.status}"
            )

    log_lines = ""
    async for log_line in kube_client.log(pod.metadata.name, namespace=pod.metadata.namespace, container="cmd"):
        log_lines += log_line
    await kube_client.delete(Pod, name=pod.metadata.name, namespace=generated_data.ess_namespace)
    return log_lines


async def wait_for_all_replicaset_replicas_ready(kube_client: AsyncClient, namespace: str):
    timeout = 30
    start_time = time.time()
    now = time.time()
    while start_time + timeout > now:
        now = time.time()
        await asyncio.sleep(0.5)
        async for rs in kube_client.list(ReplicaSet, namespace=namespace):
            if not rs.status or not rs.status.readyReplicas:
                break
            if rs.status.readyReplicas != rs.status.replicas:
                break
        else:
            return
