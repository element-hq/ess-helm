# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import time
from collections.abc import Awaitable

import pyhelm3
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import ConfigMap, Endpoints, Namespace, Secret

from ..artifacts import CertKey, generate_cert
from .utils import merge


def namespace(name: str) -> Awaitable[Namespace]:
    return Namespace(metadata=ObjectMeta(name=name))


def kubernetes_docker_secret(name: str, namespace: str, docker_config_json: str) -> Awaitable[Secret]:
    secret = Secret(
        type="kubernetes.io/dockerconfigjson",
        metadata=ObjectMeta(name=name, namespace=namespace, labels={"app.kubernetes.io/managed-by": "pytest"}),
        stringData={".dockerconfigjson": docker_config_json},
    )
    return secret


def kubernetes_tls_secret(
    name: str, namespace: str, ca: CertKey, dns_names: list[str], bundled=False
) -> Awaitable[Secret]:
    certificate = generate_cert(ca, dns_names)
    secret = Secret(
        type="kubernetes.io/tls",
        metadata=ObjectMeta(name=name, namespace=namespace, labels={"app.kubernetes.io/managed-by": "pytest"}),
        stringData={
            "tls.crt": certificate.cert_bundle_as_pem() if bundled else certificate.cert_as_pem(),
            "tls.key": certificate.key_as_pem(),
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
) -> pyhelm3.ReleaseRevision:
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
