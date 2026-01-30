# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import base64
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from ssl import SSLContext
from typing import Any
from urllib.parse import urlparse

import aiohttp
import yaml
from aiohttp_retry import JitterRetry, RetryClient
from lightkube import AsyncClient
from lightkube.generic_resource import async_load_in_cluster_generic_resources, get_generic_resource
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition
from lightkube.resources.core_v1 import Pod
from pytest_kubernetes.providers import AClusterManager

retry_options = JitterRetry(
    attempts=12,
    statuses={
        500,
        503,
    }
    | set(int(code) for code in os.environ.get("PYTEST_EXPECTED_HTTP_STATUS_CODES", "").split(",") if code),
    retry_all_server_errors=False,
)


@dataclass
class DockerAuth:
    registry: str
    username: str
    password: str


@dataclass
class KubeCtl:
    """A class to execute kubectl against a pod asynchronously"""

    cluster: AClusterManager

    async def exec(self, pod, namespace, cmd):
        return await asyncio.to_thread(
            self.cluster.kubectl, as_dict=False, args=["exec", "-t", pod, "-n", namespace, "--", *cmd]
        )


def docker_config_json(auths: list[DockerAuth]) -> str:
    docker_config_auths = {}
    for auth in auths:
        docker_config_auths[auth.registry] = {
            "username": auth.username,
            "password": auth.password,
            "auth": b64encode(f"{auth.username}:{auth.password}"),
        }

    return json.dumps({"auths": docker_config_auths})


def b64encode(value: str):
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


@asynccontextmanager
async def aiohttp_client(ssl_context: SSLContext) -> AsyncGenerator[RetryClient]:
    async with (
        aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session,
        RetryClient(session, retry_options=retry_options, raise_for_status=True) as client,
    ):
        yield client


async def aiohttp_get_json(url: str, headers: dict, ssl_context: SSLContext) -> Any:
    """Do an async HTTP GET against a url, retry exponentially on 429s. It expects a JSON response.

    Args:
        url (str): The URL to hit
        headers (dict): Any headers to add
        ssl_context (SSLContext): The SSL Context with test CA loaded

    Returns:
        Any: the Json dict response
    """
    host = urlparse(url).hostname
    if not host:
        raise ValueError(f"{url} does not have a hostname")

    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            url.replace(host, "127.0.0.1"),
            headers=headers | {"Host": host},
            server_hostname=host,
        ) as response,
    ):
        return await response.json()


async def aiohttp_post_json(url: str, data: dict, headers: dict, ssl_context: SSLContext) -> Any:
    """Do an async HTTP POST against a url, retry exponentially on 429s. IT expects a JSON resposne.

    Due to synapse bootstrap, when helm has finished deploying, HAProxy can still return
    429s because it did not detect the backend servers ready yet.

    Args:
        url (str): The URL to hit
        data (dict): The data to post
        headers (dict): Headers to use
        ssl_context (SSLContext): The SSL Context with test CA loaded

    Returns:
        Any: the Json dict response
    """
    host = urlparse(url).hostname
    if not host:
        raise ValueError("f{url} does not have a hostname")

    async with (
        aiohttp_client(ssl_context) as client,
        client.post(
            url.replace(host, "127.0.0.1"), headers=headers | {"Host": host}, server_hostname=host, json=data
        ) as response,
    ):
        # If we can 204: NO CONTENT, we dont want to try to parse json
        if response.status != 204:
            return await response.json()
        else:
            return {}


async def aiohttp_put_json(url: str, data: dict, headers: dict, ssl_context: SSLContext) -> Any:
    """Do an async HTTP PUT against a url, retry exponentially on 429s. IT expects a JSON resposne.

    Due to synapse bootstrap, when helm has finished deploying, HAProxy can still return
    429s because it did not detect the backend servers ready yet.

    Args:
        url (str): The URL to hit
        data (dict): The data to post
        headers (dict): Headers to use
        ssl_context (SSLContext): The SSL Context with test CA loaded

    Returns:
        Any: the Json dict response
    """
    host = urlparse(url).hostname
    if not host:
        raise ValueError("f{url} does not have a hostname")

    async with (
        aiohttp_client(ssl_context) as client,
        client.put(
            url.replace(host, "127.0.0.1"), headers=headers | {"Host": host}, server_hostname=host, json=data
        ) as response,
    ):
        # If we can 204: NO CONTENT, we dont want to try to parse json
        if response.status != 204:
            return await response.json()
        else:
            return {}


def merge(a: dict, b: dict, path=None):
    if not path:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif type(a[key]) is not type(b[key]):
                raise Exception("Conflict at " + ".".join(path + [str(key)]))
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def value_file_has(property_path, expected=None):
    """
    Check if a nested property (given as a dot-separated string) is would be true if the chart was installed/templated.
    """
    # If we do not have TEST_VALUES_FILE defined, we return False by default
    if not os.environ.get("TEST_VALUES_FILE"):
        return False

    with (
        open(Path().resolve() / "charts" / "matrix-stack" / "values.yaml") as base_value_file,
        open(os.environ["TEST_VALUES_FILE"]) as test_value_file,
    ):
        data = merge(yaml.safe_load(base_value_file), yaml.safe_load(test_value_file))

    keys = property_path.split(".")
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return False
    return data == expected if expected is not None else True


async def read_service_monitor_kind(kube_client):
    async for r in kube_client.list(CustomResourceDefinition):
        if r.spec.group == "monitoring.coreos.com" and r.spec.names.kind == "ServiceMonitor":
            generic_resource = get_generic_resource(f"{r.spec.group}/{r.spec.versions[0].name}", r.spec.names.kind)
            if generic_resource is None:
                await async_load_in_cluster_generic_resources(kube_client)
                generic_resource = get_generic_resource(f"{r.spec.group}/{r.spec.versions[0].name}", r.spec.names.kind)
            return generic_resource
    raise Exception("Could not find ServiceMonitor CRD")


async def get_pods_matching_labels(kube_client: AsyncClient, namespace: str, labels: dict):
    active_pods = set[str]()
    async for event, pod in kube_client.watch(Pod, namespace=namespace, labels=labels):
        assert pod
        assert pod.metadata
        assert pod.metadata.name
        assert pod.status
        assert pod.status.phase
        pod_name = pod.metadata.name
        if event in ["ADDED", "MODIFIED"] and pod_name not in active_pods and pod.status.phase == "Running":
            active_pods.add(pod_name)
            yield pod_name

        if event in ["MODIFIED", "DELETED"] and pod_name in active_pods and pod.status.phase != "Running":
            active_pods.remove(pod_name)


async def stream_logs_from_pod(kube_client: AsyncClient, namespace: str, pod_name: str, log_queue: asyncio.Queue):
    async for line in kube_client.log(pod_name, namespace=namespace, follow=True, newlines=False):
        log_queue.put_nowait(line)


async def stream_logs_from_pods_matching_labels(
    kube_client: AsyncClient, namespace: str, labels: dict[str, str], log_queue: asyncio.Queue
):
    async with asyncio.TaskGroup() as task_group:
        async for pod_name in get_pods_matching_labels(kube_client, namespace, labels):
            task_group.create_task(stream_logs_from_pod(kube_client, namespace, pod_name, log_queue))


async def forward_matching_logs(input_logs_queue: asyncio.Queue, output_matchers_to_logs_queues: list):
    while True:
        log_line = await input_logs_queue.get()
        for matcher, output_logs_queue in output_matchers_to_logs_queues:
            if matcher(log_line):
                output_logs_queue.put_nowait(log_line)
