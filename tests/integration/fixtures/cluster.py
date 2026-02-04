# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import base64
import contextlib
import os
from pathlib import Path

import httpx
import httpx_retries
import pyhelm3
import pytest
import yaml
from lightkube import ApiError, AsyncClient, KubeConfig
from lightkube.config.client_adapter import ConnectionParams, verify_cluster
from lightkube.config.kubeconfig import SingleConfig
from lightkube.core.generic_client import GenericAsyncClient
from lightkube.generic_resource import create_global_resource, create_namespaced_resource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Namespace, Secret, Service
from pytest_kubernetes.options import ClusterOptions
from pytest_kubernetes.providers import K3dManagerBase

from ..lib.utils import b64encode
from .data import ESSData

ClusterIssuer = create_global_resource(
    group="cert-manager.io",
    version="v1",
    plural="clusterissuers",
    kind="ClusterIssuer",
)

Certificate = create_namespaced_resource(
    group="cert-manager.io",
    version="v1",
    plural="certificates",
    kind="Certificate",
)


def FixedAsyncClient(config: SingleConfig, conn_parameters: ConnectionParams) -> httpx.AsyncClient:
    # A transport with a SSLContext can't be pickled. This happens with the deepcopy that `asdict` does
    # inside conn_parameters.httpx_params(). Save it off, null it out for the `asdict` and pass it explicitly
    transport: httpx.AsyncBaseTransport | None = conn_parameters.transport  # type: ignore[assignment]
    conn_parameters.transport = None
    args = conn_parameters.httpx_params(config)
    args["transport"] = transport
    return httpx.AsyncClient(**args)


GenericAsyncClient.AdapterClient = staticmethod(FixedAsyncClient)


class PotentiallyExistingK3dCluster(K3dManagerBase):
    def __init__(self, cluster_name, provider_config=None):
        super().__init__(cluster_name, provider_config)

        clusters = self._exec(["cluster", "list"])
        if any([line.startswith(cluster_name + " ") for line in clusters.stdout.decode("utf-8").split("\n")]):
            self.existing_cluster = True
        else:
            self.existing_cluster = False

    def _on_create(self, cluster_options, **kwargs):
        if self.existing_cluster:
            self._exec(
                [
                    "kubeconfig",
                    "print",
                    self.cluster_name,
                    ">",
                    str(cluster_options.kubeconfig_path),
                ]
            )
        else:
            # The cluster requires extraMounts. These are relative paths from the cluster config file
            # as they'll be different for everyone + CI.
            # We save off the current working directory incase it is important, change to the folder
            # with the cluster config file and then change back afterwards
            cwd = os.getcwd()
            try:
                fixtures_folder = Path(__file__).parent.resolve()
                os.chdir(fixtures_folder / Path("files/clusters"))
                super()._on_create(cluster_options, **kwargs)
            finally:
                os.chdir(cwd)

    def _on_delete(self):
        # We always keep around an existing cluster, it can always be deleted with scripts/destroy-test-cluster.sh
        if not self.existing_cluster and os.environ.get("PYTEST_KEEP_CLUSTER", "") != "1":
            return super()._on_delete()


@pytest.fixture(autouse=True, scope="session")
async def cluster():
    # Both these names must match what `setup_test_cluster.sh` would create
    this_cluster = PotentiallyExistingK3dCluster("ess-helm")
    this_cluster.create(
        ClusterOptions(cluster_name="ess-helm", provider_config=Path(__file__).parent / Path("files/clusters/k3d.yml"))
    )

    yield this_cluster

    this_cluster.delete()


@pytest.fixture(scope="session")
async def helm_client(cluster):
    return pyhelm3.Client(kubeconfig=cluster.kubeconfig, kubecontext=cluster.context)


@pytest.fixture(scope="session")
async def kube_client(cluster):
    kube_config = KubeConfig.from_file(cluster.kubeconfig)
    config = kube_config.get()

    # We've seen 429 errors with storage is (re)initializing. Let's retry those
    ssl_context = verify_cluster(config.cluster, config.user, config.abs_file)
    wrapped_transport = httpx.AsyncHTTPTransport(verify=ssl_context)
    transport = httpx_retries.RetryTransport(
        transport=wrapped_transport, retry=httpx_retries.Retry(status_forcelist=[429])
    )
    return AsyncClient(config=kube_config, transport=transport)


@pytest.fixture(scope="session")
async def ingress(cluster, kube_client):
    attempt = 0
    while attempt < 120:
        try:
            # We can't just kubectl wait as that doesn't work with non-existent objects
            # This can be setup before the LB port is accessible externally, so we do it afterwards
            service = await kube_client.get(Service, name="traefik", namespace="kube-system")
            await asyncio.to_thread(
                cluster.wait,
                name="service/traefik",
                waitfor="jsonpath='{.status.loadBalancer.ingress[0].ip}'",
                namespace="kube-system",
            )
            return service.spec.clusterIP
        except ApiError:
            await asyncio.sleep(1)
            attempt += 1
    raise Exception("Couldn't fetch Trafeik Service IP afrter 120s")


@pytest.fixture(autouse=True, scope="session")
async def cert_manager(helm_client, kube_client):
    if os.environ.get("SKIP_CERT_MANAGER", "false") != "false":
        return

    chart = await helm_client.get_chart("oci://quay.io/jetstack/charts/cert-manager")
    await helm_client.install_or_upgrade_release(
        "cert-manager",
        chart,
        yaml.safe_load((Path(__file__).parent / "files/charts/cert-manager.yml").open()),
        namespace="cert-manager",
        create_namespace=True,
        atomic=True,
        wait=True,
    )

    ca_folder = Path(__file__).parent.parent.parent.parent / ".ca"
    if not ca_folder.exists():
        ca_folder.mkdir()
    ca_crt_path = Path(ca_folder) / "ca.crt"
    ca_pem_path = Path(ca_folder) / "ca.pem"
    if not (ca_crt_path.exists() and ca_pem_path.exists()):
        await kube_client.create(ClusterIssuer(metadata={"name": "ess-ca"}, spec={"selfSigned": {}}))
        await kube_client.create(
            Certificate(
                metadata={"name": "ess-ca", "namespace": "cert-manager"},
                spec={
                    "isCA": True,
                    "commonName": "ess-ca",
                    "secretName": "ess-ca",
                    "duration": "87660h0m0s",
                    "privateKey": {"algorithm": "RSA"},
                    "issuerRef": {"name": "ess-ca", "kind": "ClusterIssuer", "group": "cert-manager.io"},
                },
            )
        )

        # Wait for certificate to be ready
        cert_ready = False
        while not cert_ready:
            cert = await kube_client.get(Certificate, name="ess-ca", namespace="cert-manager")
            if cert.status and cert.status.get("conditions"):
                for condition in cert.status["conditions"]:
                    if condition["type"] == "Ready" and condition["status"] == "True":
                        cert_ready = True
                        break
            await asyncio.sleep(1)
    else:
        # Delete existing resources
        with contextlib.suppress(Exception):
            await kube_client.delete(ClusterIssuer, name="ess-ca")
        with contextlib.suppress(Exception):
            await kube_client.delete(Certificate, name="ess-ca", namespace="cert-manager")
        with contextlib.suppress(Exception):
            await kube_client.delete(Secret, name="ess-ca", namespace="cert-manager")

        await kube_client.create(
            Secret(
                metadata=ObjectMeta(name="ess-ca", namespace="cert-manager"),
                data={
                    "tls.crt": b64encode(ca_crt_path.read_text()),
                    "tls.key": b64encode(ca_pem_path.read_text()),
                    "ca.crt": b64encode(ca_crt_path.read_text()),
                },
            )
        )
    await kube_client.apply(
        ClusterIssuer(metadata={"name": "ess-selfsigned"}, spec={"ca": {"secretName": "ess-ca"}}),
        field_manager="pytest",
    )
    ess_ca_secret = await kube_client.get(Secret, name="ess-ca", namespace="cert-manager")

    if not ca_crt_path.exists() or not ca_pem_path.exists():
        with open(ca_crt_path, "w") as crt_file, open(ca_pem_path, "w") as pem_file:
            crt_file.write(base64.standard_b64decode(ess_ca_secret.data["ca.crt"]).decode("utf-8"))
            pem_file.write(base64.standard_b64decode(ess_ca_secret.data["tls.key"]).decode("utf-8"))


@pytest.fixture(scope="session")
async def prometheus_operator_crds(helm_client):
    if os.environ.get("SKIP_SERVICE_MONITORS_CRDS", "false") == "false":
        chart = await helm_client.get_chart("oci://ghcr.io/prometheus-community/charts/prometheus-operator-crds")

        # Install or upgrade a release
        await helm_client.install_or_upgrade_release(
            "prometheus-operator-crds",
            chart,
            {},
            namespace="prometheus-operator",
            create_namespace=True,
            atomic=True,
            wait=True,
        )


@pytest.fixture(scope="session")
async def ess_namespace(cluster: PotentiallyExistingK3dCluster, kube_client: AsyncClient, generated_data: ESSData):
    (major_version, minor_version) = cluster.version()
    try:
        await kube_client.get(Namespace, name=generated_data.ess_namespace)
    except ApiError:
        await kube_client.create(
            Namespace(
                metadata=ObjectMeta(
                    name=generated_data.ess_namespace,
                    labels={
                        "app.kubernetes.io/managed-by": "pytest",
                        # We do turn on enforce here to cause test failures.
                        # If we actually need restricted functionality then the tests can drop this
                        # and parse the audit logs
                        "pod-security.kubernetes.io/enforce": "restricted",
                        "pod-security.kubernetes.io/enforce-version": f"v{major_version}.{minor_version}",
                        "pod-security.kubernetes.io/audit": "restricted",
                        "pod-security.kubernetes.io/audit-version": f"v{major_version}.{minor_version}",
                        "pod-security.kubernetes.io/warn": "restricted",
                        "pod-security.kubernetes.io/warn-version": f"v{major_version}.{minor_version}",
                    },
                )
            )
        )

    yield

    if os.environ.get("PYTEST_KEEP_CLUSTER", "") != "1":
        await kube_client.delete(Namespace, name=generated_data.ess_namespace)
