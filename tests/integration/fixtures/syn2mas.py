# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import base64
import os

import pyhelm3
import pytest
import yaml
from lightkube import AsyncClient
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Namespace, Secret, Service
from lightkube.resources.networking_v1 import Ingress

from ..lib.helpers import kubernetes_docker_secret, kubernetes_tls_secret, wait_for_endpoint_ready
from ..lib.utils import DockerAuth, docker_config_json, value_file_has
from .data import ESSData


@pytest.fixture(autouse=True, scope="session")
async def upgrade_enable_syn2mas(
    helm_client: pyhelm3.Client,
    ingress,
    helm_prerequisites,
    ess_namespace: Namespace,
    generated_data: ESSData,
    loaded_matrix_tools: dict,
):
    revision = await helm_client.get_current_revision(generated_data.release_name, namespace=generated_data.ess_namespace)
    values = revision.values
    values.setdefault("matrixAuthenticationService", {})["enabled"] = True
    values["matrixAuthenticationService"].setdefault("syn2mas", {})["enabled"] = True
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED



@pytest.fixture(autouse=True, scope="session")
async def upgrade_migrate_dryrun_syn2mas(
    helm_client: pyhelm3.Client,
    ingress,
    helm_prerequisites,
    upgrade_enable_syn2mas,
    ess_namespace: Namespace,
    generated_data: ESSData,
    loaded_matrix_tools: dict,
):
    revision = await helm_client.get_current_revision(generated_data.release_name, namespace=generated_data.ess_namespace)
    values = revision.values
    values["matrixAuthenticationService"]["syn2mas"].setdefault("migrate")["enabled"] = True
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED


@pytest.fixture(autouse=True, scope="session")
async def upgrade_migrate_syn2mas(
    helm_client: pyhelm3.Client,
    ingress,
    helm_prerequisites,
    upgrade_enable_syn2mas,
    ess_namespace: Namespace,
    generated_data: ESSData,
    loaded_matrix_tools: dict,
):
    revision = await helm_client.get_current_revision(generated_data.release_name, namespace=generated_data.ess_namespace)
    values = revision.values
    values["matrixAuthenticationService"]["syn2mas"].setdefault("migrate")["dryRun"] = False
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED


@pytest.fixture(autouse=True, scope="session")
async def upgrade_final_syn2mas(
    helm_client: pyhelm3.Client,
    ingress,
    helm_prerequisites,
    upgrade_enable_syn2mas,
    ess_namespace: Namespace,
    generated_data: ESSData,
    loaded_matrix_tools: dict,
):
    revision = await helm_client.get_current_revision(generated_data.release_name, namespace=generated_data.ess_namespace)
    values = revision.values
    values["matrixAuthenticationService"]["syn2mas"]["enabled"] = False
    chart = await helm_client.get_chart("charts/matrix-stack")
    # Install or upgrade a release
    revision = await helm_client.install_or_upgrade_release(
        generated_data.release_name,
        chart,
        values,
        namespace=generated_data.ess_namespace,
        atomic="CI" not in os.environ,
        wait=True,
    )
    assert revision.status == pyhelm3.ReleaseRevisionStatus.DEPLOYED
