# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_workload_parts, template_id


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

        assert "failureThreshold" in probe, (
            f"{template_id(template)} has container {container['name']} with a {probe_type} missing a failureThreshold"
        )
        assert "periodSeconds" in probe, (
            f"{template_id(template)} has container {container['name']} with a {probe_type} missing a periodSeconds"
        )
        assert "successThreshold" in probe, (
            f"{template_id(template)} has container {container['name']} with a {probe_type} missing a successThreshold"
        )
        assert "timeoutSeconds" in probe, (
            f"{template_id(template)} has container {container['name']} with a {probe_type} missing a timeoutSeconds"
        )

        # We use startupProbes for this
        assert "initialDelaySeconds" not in probe, (
            f"{template_id(template)} has container {container['name']} with {probe_type}.initialDelaySeconds set "
            "when we should be using a startupProbe"
        )

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


def assert_matching_probe(template, probe_type, values, template_to_deployable_details):
    for container in template["spec"]["template"]["spec"]["containers"]:
        assert probe_type in container, (
            f"{template_id(template)} has container {container['name']} without a {probe_type}"
        )

        deployable_details = template_to_deployable_details(template, container["name"])
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
async def test_livenessProbes_are_configurable(values, make_templates, template_to_deployable_details):
    set_probe_details(values, PropertyType.LivenessProbe)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_matching_probe(template, "livenessProbe", values, template_to_deployable_details)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_readinessProbes_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_sensible_default_probe(template, "readinessProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_readinessProbes_are_configurable(values, make_templates, template_to_deployable_details):
    set_probe_details(values, PropertyType.ReadinessProbe)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_matching_probe(template, "readinessProbe", values, template_to_deployable_details)


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sensible_startupProbes_by_default(templates):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_sensible_default_probe(template, "startupProbe")


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_startupProbes_are_configurable(values, make_templates, template_to_deployable_details):
    set_probe_details(values, PropertyType.StartupProbe)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet"]:
            assert_matching_probe(template, "startupProbe", values, template_to_deployable_details)
