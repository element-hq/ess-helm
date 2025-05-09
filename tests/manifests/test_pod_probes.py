# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any, Callable

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, iterate_synapse_workers_parts, template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_jobs(templates):
    for template in templates:
        if template["kind"] == "Job":
            for container in template["spec"]["template"]["spec"]["containers"]:
                assert "livenessProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a livenessProbe"
                )
                assert "readinessProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a readinessProbe"
                )
                assert "startupProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a startupProbe"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_initContainers(templates):
    for template in templates:
        if template["kind"] == ["Deployment", "StatefulSet"]:
            for init_container in template["spec"]["template"]["spec"].get("initContainers", []):
                assert "livenessProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a livenessProbe"
                )
                assert "readinessProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a readinessProbe"
                )
                assert "startupProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a startupProbe"
                )


def assert_sensible_default_probe(template, probe_type):
    for container in template["spec"]["template"]["spec"]["containers"]:
        assert probe_type in container, (
            f"{template_id(template)} has container {container['name']} without a {probe_type}"
        )
        probe = container[probe_type]

        assert "httpGet" in probe or "exec" in probe or "tcpSocket" in probe
        if "httpGet" in probe:
            assert "port" in probe["httpGet"], (
                f"{template_id(template)} has container {container['name']} whose "
                "{probe_type}.http which doesn't specify a port"
            )

            probePort = probe["httpGet"]["port"]
            assert isinstance(probePort, str), (
                f"{template_id(template)} has container {container['name']} whose "
                "{probe_type}.httpGet.port isn't a named port"
            )

            assert any([port["name"] == probePort for port in container["ports"]])


def set_probe_details(deployables_details, values, probe_type):
    deployable_details_to_probe_details = {}

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
        deployable_details_to_probe_details[deployable_details] = probe_details
        deployable_details.set_helm_values(values, probe_type, probe_details)

    iterate_deployables_workload_parts(deployables_details, set_probe_details)
    return deployable_details_to_probe_details


def set_synapse_probe_details(all_values, probe_type):
    worker_to_probe_details = {}

    # We have a counter that increments for each probe field for each worker
    # That way we can assert a) the correct value is going into the correct field and
    # b) that the correct part of the values file is being used
    counter = 100

    def set_probe_details(worker_name, values):
        nonlocal counter
        probe_details = {
            "failureThreshold": counter,
            "initialDelaySeconds": counter + 1,
            "periodSeconds": counter + 2,
            # livenessProbes can only set this to 1 (or absent which then defaults to 1)
            "successThreshold": None if probe_type in [PropertyType.LivenessProbe] else counter + 3,
            "timeoutSeconds": counter + 4,
        }
        counter += 5
        worker_to_probe_details[worker_name] = probe_details
        values[probe_type.value] = probe_details

    iterate_synapse_workers_parts(all_values, set_probe_details)
    return worker_to_probe_details


def deployable_details_probe_fetcher(deployable_details_to_probe_details, template_to_deployable_details):
    def probe_details_fetcher(template, container_name):
        deployable_details = template_to_deployable_details(template, container_name)
        return deployable_details_to_probe_details[deployable_details]

    return probe_details_fetcher


def synapse_worker_probe_fetcher(release_name, worker_to_probe_details):
    def probe_details_fetcher(template, _):
        worker_name = template["metadata"]["name"].replace(f"{release_name}-synapse-", "")
        return worker_to_probe_details[worker_name]

    return probe_details_fetcher


def assert_matching_probe(template, probe_type, probe_details_fetcher: Callable[[dict[str, Any], str], dict[str, Any]]):
    for container in template["spec"]["template"]["spec"]["containers"]:
        assert probe_type in container, (
            f"{template_id(template)} has container {container['name']} without a {probe_type}"
        )

        probe_details = probe_details_fetcher(template, container["name"])
        probe = container[probe_type]

        for key, value in probe_details.items():
            if value is not None:
                assert key in probe, (
                    f"{template_id(template)} has container {container['name']} with a {probe_type} missing a {key}"
                )
                assert value == probe[key], (
                    f"{template_id(template)} has container {container['name']} with {probe_type}.{key} "
                    f"where {probe[key]} != {value}"
                )
            else:
                assert key not in probe, (
                    f"{template_id(template)} has container {container['name']} with a {probe_type} "
                    f"with {key} present when it should be absent"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_livenessProbes_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_sensible_default_probe(template, "livenessProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_livenessProbes_are_configurable(
    deployables_details, values, make_templates, template_to_deployable_details
):
    deployable_details_to_probe_details = set_probe_details(deployables_details, values, PropertyType.LivenessProbe)
    for template in await make_templates(values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name != "synapse"
        ):
            assert_matching_probe(
                template,
                "livenessProbe",
                deployable_details_probe_fetcher(deployable_details_to_probe_details, template_to_deployable_details),
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_synapse_livenessProbes_are_configurable(
    all_values, release_name, make_templates, template_to_deployable_details
):
    workers_to_probe_details = set_synapse_probe_details(all_values, PropertyType.LivenessProbe)
    for template in await make_templates(all_values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name == "synapse"
        ):
            assert_matching_probe(
                template, "livenessProbe", synapse_worker_probe_fetcher(release_name, workers_to_probe_details)
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_readinessProbes_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_sensible_default_probe(template, "readinessProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_readinessProbes_are_configurable(
    deployables_details, values, make_templates, template_to_deployable_details
):
    deployable_details_to_probe_details = set_probe_details(deployables_details, values, PropertyType.ReadinessProbe)
    for template in await make_templates(values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name != "synapse"
        ):
            assert_matching_probe(
                template,
                "readinessProbe",
                deployable_details_probe_fetcher(deployable_details_to_probe_details, template_to_deployable_details),
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_synapse_readinessProbes_are_configurable(
    all_values, release_name, make_templates, template_to_deployable_details
):
    workers_to_probe_details = set_synapse_probe_details(all_values, PropertyType.ReadinessProbe)
    for template in await make_templates(all_values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name == "synapse"
        ):
            assert_matching_probe(
                template, "readinessProbe", synapse_worker_probe_fetcher(release_name, workers_to_probe_details)
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_startupProbes_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_sensible_default_probe(template, "startupProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_startupProbes_are_configurable(
    deployables_details, values, make_templates, template_to_deployable_details
):
    deployable_details_to_probe_details = set_probe_details(deployables_details, values, PropertyType.StartupProbe)
    for template in await make_templates(values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name != "synapse"
        ):
            assert_matching_probe(
                template,
                "startupProbe",
                deployable_details_probe_fetcher(deployable_details_to_probe_details, template_to_deployable_details),
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_synapse_startupProbes_are_configurable(
    all_values, release_name, make_templates, template_to_deployable_details
):
    workers_to_probe_details = set_synapse_probe_details(all_values, PropertyType.StartupProbe)
    for template in await make_templates(all_values):
        if (
            template["kind"] in ["Deployment", "StatefulSet"]
            and template_to_deployable_details(template).name == "synapse"
        ):
            assert_matching_probe(
                template, "startupProbe", synapse_worker_probe_fetcher(release_name, workers_to_probe_details)
            )
