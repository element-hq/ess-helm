# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import deepfreeze

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_gets_configured_extraInitContainers(values, make_templates):
    template_id_to_init_containers = {}
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        template_id_to_init_containers[pod_template_details.manifest_id] = deepfreeze(
            pod_spec.get("initContainers", [])
        )

    def set_initContainers(deployable_details: DeployableDetails):
        init_container = [
            {"name": f"{deployable_details.name}-extra", "image": "oci.element.io/extra-image:v1.2.3"},
            {
                "name": f"aaa-{deployable_details.name}-extra",
                "image": "oci.element.io/another-extra-image:v1.2.3",
                "env": [{"name": "A", "value": "B"}, {"name": "FOO", "value": "BAR"}],
            },
        ]
        deployable_details.set_helm_values(values, PropertyType.InitContainers, deepfreeze(init_container))

    iterate_deployables_workload_parts(set_initContainers)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "initContainers" in pod_spec, (
            f"{pod_template_details.manifest_id} doesn't have at least one initContainers "
            "when a custom one is configured"
        )
        init_containers = pod_spec["initContainers"]

        deployable_details = pod_template_details.deployable_details()
        extra_init_containers = deployable_details.get_helm_values(values, PropertyType.InitContainers)
        # All the existing initContainers come first
        assert (
            template_id_to_init_containers[pod_template_details.manifest_id] + extra_init_containers
        ) == init_containers


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_redis_components_have_valkey_wait_init_container(values, make_templates):

    def _synapse_uses_redis() -> bool:
        # Synapse only connects to Redis/Valkey when workers are running
        workers = values.get("synapse", {}).get("workers", {})
        workers_enabled = any(worker.get("enabled", False) for worker in workers.values())
        return workers_enabled

    for pod_template_details in iterate_pod_template(await make_templates(values)):
        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.has_redis:
            continue
        if deployable_details.is_synapse_process and not _synapse_uses_redis():
            continue
        pod_spec = pod_template_details.pod_template["spec"]
        init_container_names = [container["name"] for container in pod_spec.get("initContainers", [])]
        assert "valkey-wait" in init_container_names, (
            f"{pod_template_details.manifest_id} uses Redis/Valkey but doesn't wait for it "
            "with a valkey-wait initContainer"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_db_components_have_db_wait_init_container(values, make_templates):
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.has_db:
            continue
        pod_spec = pod_template_details.pod_template["spec"]
        init_container_names = [container["name"] for container in pod_spec.get("initContainers", [])]
        # The syn2mas job waits for two databases, so its containers are named
        # db-wait-mas and db-wait-syn. Other components use plain db-wait.
        assert any(name.startswith("db-wait") for name in init_container_names), (
            f"{pod_template_details.manifest_id} uses Postgres but doesn't wait for it with a db-wait initContainer"
        )
