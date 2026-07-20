# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import (
    EPHEMERAL_WORKLOAD_KINDS,
    PERSISTENT_WORKLOAD_KINDS,
    PodTemplateDetails,
    iterate_deployables_workload_parts,
    iterate_pod_template,
)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_jobs(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=EPHEMERAL_WORKLOAD_KINDS):
        for container in pod_template_details.pod_template["spec"]["containers"]:
            assert "livenessProbe" not in container, (
                f"{pod_template_details.manifest_id} has container {container['name']} with a livenessProbe"
            )
            assert "readinessProbe" not in container, (
                f"{pod_template_details.manifest_id} has container {container['name']} with a readinessProbe"
            )
            assert "startupProbe" not in container, (
                f"{pod_template_details.manifest_id} has container {container['name']} with a startupProbe"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_initContainers(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        for init_container in pod_template_details.pod_template["spec"].get("initContainers", []):
            assert "livenessProbe" not in init_container, (
                f"{pod_template_details.manifest_id} has initContainer {init_container['name']} with a livenessProbe"
            )
            assert "readinessProbe" not in init_container, (
                f"{pod_template_details.manifest_id} has initContainer {init_container['name']} with a readinessProbe"
            )
            assert "startupProbe" not in init_container, (
                f"{pod_template_details.manifest_id} has initContainer {init_container['name']} with a startupProbe"
            )


def assert_sensible_default_probe(pod_template_details: PodTemplateDetails, probe_type):
    for container in pod_template_details.pod_template["spec"]["containers"]:
        assert probe_type in container, (
            f"{pod_template_details.manifest_id} has container {container['name']} without a {probe_type}"
        )
        probe = container[probe_type]

        assert "failureThreshold" in probe, (
            f"{pod_template_details.manifest_id} has container {container['name']} with a "
            f"{probe_type} missing a failureThreshold"
        )
        assert "periodSeconds" in probe, (
            f"{pod_template_details.manifest_id} has container {container['name']} with a "
            f"{probe_type} missing a periodSeconds"
        )
        assert "successThreshold" in probe, (
            f"{pod_template_details.manifest_id} has container {container['name']} with a "
            f"{probe_type} missing a successThreshold"
        )
        assert "timeoutSeconds" in probe, (
            f"{pod_template_details.manifest_id} has container {container['name']} with a "
            f"{probe_type} missing a timeoutSeconds"
        )

        # We use startupProbes for this
        assert "initialDelaySeconds" not in probe, (
            f"{pod_template_details.manifest_id} has container {container['name']} with "
            f"{probe_type}.initialDelaySeconds set when we should be using a startupProbe"
        )

        assert "httpGet" in probe or "exec" in probe or "tcpSocket" in probe
        if "httpGet" in probe:
            assert "port" in probe["httpGet"], (
                f"{pod_template_details.manifest_id} has container {container['name']} whose "
                "{probe_type}.http which doesn't specify a port"
            )

            probePort = probe["httpGet"]["port"]
            assert isinstance(probePort, str), (
                f"{pod_template_details.manifest_id} has container {container['name']} whose "
                "{probe_type}.httpGet.port isn't a named port"
            )

            assert any([port["name"] == probePort for port in container["ports"]])


def set_probe_details(values, probe_type):
    # We have a counter that increments for each probe field for each deployable details
    # That way we can assert a) the correct value is going into the correct field and
    # b) that the correct part of the values file is being used
    counter = 100

    def set_probe_details(deployable_details: DeployableDetails):
        nonlocal counter
        probe_details = {
            "failureThreshold": counter,
            "initialDelaySeconds": counter + 1,
            "periodSeconds": counter + 2,
            # livenessProbes & startupProbes can only set this to 1 (or absent which then defaults to 1)
            "successThreshold": None
            if probe_type in [PropertyType.LivenessProbe, PropertyType.StartupProbe]
            else counter + 3,
            "timeoutSeconds": counter + 4,
        }
        counter += 5
        deployable_details.set_helm_values(values, probe_type, probe_details)

    iterate_deployables_workload_parts(set_probe_details)


def assert_matching_probe(pod_template_details: PodTemplateDetails, probe_type, values):
    for container in pod_template_details.pod_template["spec"]["containers"]:
        assert probe_type in container, (
            f"{pod_template_details.manifest_id} has container {container['name']} without a {probe_type}"
        )

        deployable_details = pod_template_details.deployable_details(container["name"])
        probe_types_to_property_types = {
            "livenessProbe": PropertyType.LivenessProbe,
            "readinessProbe": PropertyType.ReadinessProbe,
            "startupProbe": PropertyType.StartupProbe,
        }
        probe_details = deployable_details.get_helm_values(values, probe_types_to_property_types[probe_type])
        probe = container[probe_type]

        for key, value in probe_details.items():
            if value is not None:
                assert key in probe, (
                    f"{pod_template_details.manifest_id} has container {container['name']} with a {probe_type} "
                    f"missing a {key}"
                )
                assert value == probe[key], (
                    f"{pod_template_details.manifest_id} has container {container['name']} with {probe_type}.{key} "
                    f"where {probe[key]} != {value}"
                )
            else:
                assert key not in probe, (
                    f"{pod_template_details.manifest_id} has container {container['name']} with a {probe_type} "
                    f"with {key} present when it should be absent"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_livenessProbes_by_default(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_sensible_default_probe(pod_template_details, "livenessProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_livenessProbes_are_configurable(values, make_templates):
    set_probe_details(values, PropertyType.LivenessProbe)
    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_matching_probe(pod_template_details, "livenessProbe", values)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_readinessProbes_by_default(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_sensible_default_probe(pod_template_details, "readinessProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_readinessProbes_are_configurable(values, make_templates):
    set_probe_details(values, PropertyType.ReadinessProbe)
    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_matching_probe(pod_template_details, "readinessProbe", values)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_startupProbes_by_default(templates):
    for pod_template_details in iterate_pod_template(templates, kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_sensible_default_probe(pod_template_details, "startupProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_startupProbes_are_configurable(values, make_templates):
    set_probe_details(values, PropertyType.StartupProbe)
    for pod_template_details in iterate_pod_template(await make_templates(values), kinds=PERSISTENT_WORKLOAD_KINDS):
        assert_matching_probe(pod_template_details, "startupProbe", values)
