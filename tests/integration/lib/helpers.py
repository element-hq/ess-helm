# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import time
from collections.abc import Awaitable

from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Endpoints, Namespace, Secret

from ..artifacts import CertKey, generate_cert


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
