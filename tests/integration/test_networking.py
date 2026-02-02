# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os

import pytest
from lightkube import AsyncClient
from lightkube import operators as op
from lightkube.resources.apps_v1 import ReplicaSet
from lightkube.resources.core_v1 import Pod, Service
from prometheus_client.parser import text_string_to_metric_families

from .fixtures.data import ESSData
from .lib.helpers import run_pod_with_args, wait_for_all_deployments_rolled_out, wait_for_endpoint_ready
from .lib.utils import read_service_monitor_kind


@pytest.mark.asyncio_cooperative
async def test_services_have_matching_labels(kube_client: AsyncClient, generated_data: ESSData, matrix_stack):
    ignored_labels = [
        "app.kubernetes.io/managed-by",
        "helm.sh/chart",
        "k8s.element.io/service-type",
        "k8s.element.io/synapse-instance",
        "replica",
    ]

    async for service in kube_client.list(
        Service, namespace=generated_data.ess_namespace, labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])}
    ):
        assert service.spec, f"Encountered a service without spec : {service}"
        assert service.spec.selector, f"Encountered a service missing a selector : {service}"
        assert service.metadata, f"Encountered a service without metadata : {service}"
        assert service.metadata.labels, f"Encountered a service without labels : {service}"
        label_selectors = {label: value for label, value in service.spec.selector.items()}

        async for pod in kube_client.list(Pod, namespace=generated_data.ess_namespace, labels=label_selectors):
            if pod.status and pod.status.phase in ("Terminating", "Succeeded"):
                continue  # Skip terminating pods
            # For Pods part of a replicaset we must ignore pods which template-hash do not match
            # the latest replicaset `pod-template-hash`
            if pod.metadata and pod.metadata.labels and pod.metadata.labels.get("pod-template-hash"):
                async for rs in kube_client.list(
                    ReplicaSet,
                    namespace=generated_data.ess_namespace,
                    labels={"pod-template-hash": op.equal(pod.metadata.labels["pod-template-hash"])},
                ):
                    # we check if the rs desires replicas
                    if rs.spec and rs.spec.replicas:
                        break
                else:
                    # Skip pods which do not have a ReplicaSet desiring replicas
                    continue
            assert service.metadata, f"Encountered a service without metadata : {service}"
            assert pod.metadata, f"Encountered a pod without metadata : {pod}"
            assert pod.metadata.labels, f"Encountered a pod without labels : {pod}"
            has_target_label = any(label.startswith("k8s.element.io/target-") for label in service.metadata.labels)
            for label, value in service.metadata.labels.items():
                if label in ["k8s.element.io/owner-name", "k8s.element.io/owner-group-kind"]:
                    assert label not in pod.metadata.labels
                    continue
                elif label in ignored_labels or (
                    has_target_label and label in ["app.kubernetes.io/name", "app.kubernetes.io/instance"]
                ):
                    continue
                assert label.replace("k8s.element.io/target-", "app.kubernetes.io/") in pod.metadata.labels
                assert value.startswith(
                    pod.metadata.labels[label.replace("k8s.element.io/target-", "app.kubernetes.io/")]
                ), (
                    f"Service/{service.metadata.name} has {label=}={value=} "
                    f"which does not start with the value from the Pod/{pod.metadata.name} "
                    f"{label.replace('k8s.element.io/target-', 'app.kubernetes.io/')}="
                    f"{pod.metadata.labels[label.replace('k8s.element.io/target-', 'app.kubernetes.io/')]} "
                    f"(pod status phase : {pod.status.phase if pod.status else 'N/A'}"
                )


@pytest.mark.asyncio_cooperative
async def test_services_have_endpoints(cluster, kube_client: AsyncClient, generated_data: ESSData, matrix_stack):
    # Helm will stop waiting when 1 of replicas are ready
    # We need to wait for all replicas to be ready to check that services all have endpoints
    await wait_for_all_deployments_rolled_out(kube_client, generated_data.ess_namespace)
    endpoints_to_wait = []
    services = {}
    async for service in kube_client.list(
        Service, namespace=generated_data.ess_namespace, labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])}
    ):
        assert service.metadata, f"Encountered a service without metadata : {service}"
        assert service.spec, f"Encountered a service without spec : {service}"
        endpoints_to_wait.append(
            wait_for_endpoint_ready(service.metadata.name, generated_data.ess_namespace, cluster, kube_client)
        )
        services[service.metadata.name] = service

    for endpoint in await asyncio.gather(*endpoints_to_wait):
        assert endpoint.metadata is not None, f"Encountered an endpoint without metadata : {endpoint}"
        assert endpoint.subsets, f"Endpoint {endpoint.metadata.name} has no subsets"

        ports = []
        for subset in endpoint.subsets:
            assert subset.addresses, f"Endpoint {endpoint.metadata.name} has no addresses"
            assert not subset.notReadyAddresses, f"Endpoint {endpoint.metadata.name} has notReadyAddresses"
            assert subset.ports, f"Endpoint {endpoint.metadata.name} has no ports"
            ports += subset.ports

        port_names = [port.name for port in ports if port.name]
        port_numbers = [port.port for port in ports]
        service_from_endpoint = services[endpoint.metadata.name]
        assert service_from_endpoint.spec, f"Service {endpoint.metadata.name} has no spec"
        assert service_from_endpoint.spec.ports, f"Service {endpoint.metadata.name} has no port"
        for port in service_from_endpoint.spec.ports:
            if port.name:
                assert port.name in port_names
            else:
                assert port.port in port_numbers


@pytest.mark.skipif(
    os.environ.get("SKIP_SERVICE_MONITORS_CRDS", "false") == "true", reason="ServiceMonitors not deployed"
)
@pytest.mark.asyncio_cooperative
@pytest.mark.usefixtures("matrix_stack")
async def test_pods_monitored(
    kube_client: AsyncClient,
    generated_data: ESSData,
):
    # Helm will stop waiting when 1 of replicas are ready
    # We need to wait for all replicas to be ready to be able to compute monitorable and monitored pods
    await wait_for_all_deployments_rolled_out(kube_client, generated_data.ess_namespace)
    all_running_pods = list[Pod]()
    all_monitorable_pod_names = set[str]()
    async for pod in kube_client.list(
        Pod, namespace=generated_data.ess_namespace, labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])}
    ):
        if pod.status and pod.status.phase in ("Terminating", "Succeeded"):
            continue  # Skip terminating pods

        elif pod.metadata:
            assert pod.metadata.name, "Encountered a pod without a name"
            all_running_pods.append(pod)

            if pod.metadata.annotations and "has-no-service-monitor" in pod.metadata.annotations:
                continue

            all_monitorable_pod_names.add(pod.metadata.name)
        else:
            raise RuntimeError(f"Pod {pod} has no metadata")

    monitored_pod_names = set[str]()
    async for service_monitor in kube_client.list(
        await read_service_monitor_kind(kube_client),
        namespace=generated_data.ess_namespace,
        labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])},
    ):
        service_monitor_is_useful = False
        async for service in kube_client.list(
            Service, namespace=generated_data.ess_namespace, labels=service_monitor["spec"]["selector"]["matchLabels"]
        ):
            assert service.metadata, f"Encountered a service without metadata : {service}"
            assert service.spec, f"Encountered a service without spec : {service}"
            assert service.spec.ports, f"Ecountered a service without port : {service}"
            assert service.spec.selector, f"Ecountered a service without selectors : {service}"

            for endpoint in service_monitor["spec"]["endpoints"]:
                service_port_names = [port.name for port in service.spec.ports if port.name]
                if endpoint["port"] in service_port_names:
                    break

            def matches_labels(pod, selector):
                pod_labels = pod.metadata.labels
                for label, value in selector.items():
                    if label not in pod_labels:
                        return False

                    if pod_labels[label] != value:
                        return False
                return True

            for covered_pod in [pod for pod in all_running_pods if matches_labels(pod, service.spec.selector)]:
                assert covered_pod.metadata
                if not covered_pod.metadata:
                    raise RuntimeError(f"Pod {covered_pod} has no metadata")

                # Something monitored by multiple ServiceMonitors smells like a bug
                assert covered_pod.metadata.name not in monitored_pod_names, (
                    f"Pod {covered_pod.metadata.name} is monitored multiple times"
                )
                assert covered_pod.metadata.name
                monitored_pod_names.add(covered_pod.metadata.name)
                service_monitor_is_useful = True

        assert service_monitor_is_useful, f"ServiceMonitor {service_monitor['metadata']['name']} does not cover any pod"

    assert all_monitorable_pod_names == monitored_pod_names, (
        f"Some pods are not monitored : {', '.join(list(set(all_monitorable_pod_names) ^ set(monitored_pod_names)))}"
    )


@pytest.mark.skipif(
    os.environ.get("SKIP_SERVICE_MONITORS_CRDS", "false") == "true", reason="ServiceMonitors not deployed"
)
@pytest.mark.skipif(os.environ.get("MATRIX_TEST_FROM_REF", "") == "25.6.2", reason="This fails against 25.6.2.")
@pytest.mark.asyncio_cooperative
@pytest.mark.usefixtures("matrix_stack")
async def test_service_monitors_point_to_metrics(
    kube_client: AsyncClient,
    generated_data: ESSData,
):
    async for service_monitor in kube_client.list(
        await read_service_monitor_kind(kube_client),
        namespace=generated_data.ess_namespace,
        labels={"app.kubernetes.io/part-of": op.in_(["matrix-stack"])},
    ):
        found_metrics = False
        async for service in kube_client.list(
            Service, namespace=generated_data.ess_namespace, labels=service_monitor["spec"]["selector"]["matchLabels"]
        ):
            assert service.metadata, f"Encountered a service without metadata : {service}"
            assert service.spec, f"Encountered a service without spec : {service}"
            assert service.spec.ports, f"Ecountered a service without port : {service}"
            assert service.spec.selector, f"Ecountered a service without selectors : {service}"

            for endpoint in service_monitor["spec"]["endpoints"]:
                service_port_names = [port.name for port in service.spec.ports if port.name]
                if endpoint["port"] in service_port_names:
                    assert await has_actual_metrics_on_endpoint(
                        kube_client, generated_data, service, service_monitor["spec"]["endpoints"]
                    )
                    found_metrics = True
        assert found_metrics, (
            f"ServiceMonitor {service_monitor['metadata']['name']} does not point to any /metrics endpoint"
        )


async def has_actual_metrics_on_endpoint(
    kube_client: AsyncClient, generated_data: ESSData, service: Service, endpoints
):
    assert service.metadata
    assert service.spec
    assert service.spec.ports
    found_metrics = False
    for endpoint in endpoints:
        for port_spec in service.spec.ports:
            if port_spec.name == endpoint["port"]:
                metrics_data = await run_pod_with_args(
                    kube_client,
                    generated_data,
                    "curlimages/curl:latest",
                    "curl",
                    [
                        "-s",
                        "--connect-timeout",
                        "2",
                        "--max-time",
                        "5",
                        f"http://{service.metadata.name}.{generated_data.ess_namespace}.svc.cluster.local:{port_spec.port}/metrics",
                    ],
                    restart_policy="OnFailure",
                )
                for metric_family in text_string_to_metric_families(metrics_data):
                    assert metric_family.name, "Metric family has no name"
                found_metrics = True
    return found_metrics
