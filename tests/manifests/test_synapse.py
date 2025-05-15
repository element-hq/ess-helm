# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


from typing import Any, Callable

import pytest
import yaml

from . import DeployableDetails, PropertyType
from .utils import (
    iterate_deployables_ingress_parts,
    iterate_synapse_workers_parts,
    template_id,
)


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_configmaps_are_templated(release_name, values, make_templates):
    values["synapse"].setdefault("appservices", []).append(
        {"configMap": "as-{{ $.Release.Name }}", "configMapKey": "reg.yaml"}
    )

    for template in await make_templates(values):
        if template["metadata"]["name"].startswith(f"{release_name}-synapse") and template["kind"] == "StatefulSet":
            for volume in template["spec"]["template"]["spec"]["volumes"]:
                if (
                    "configMap" in volume
                    and volume["configMap"]["name"] == f"as-{release_name}"
                    and volume["name"] == "as-0"
                ):
                    break
            else:
                raise AssertionError(
                    "The appservice configMap wasn't included in the volumes : "
                    f"{','.join([volume['name'] for volume in template['spec']['template']['spec']['volumes']])}"
                )

            for volumeMount in template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]:
                if volumeMount["name"] == "as-0" and volumeMount["mountPath"] == "/as/0/reg.yaml":
                    break
            else:
                raise AssertionError("The appservice configMap isn't mounted at the expected location")


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_appservice_secrets_are_templated(release_name, values, make_templates):
    values["synapse"].setdefault("appservices", []).append(
        {"secret": "as-{{ $.Release.Name }}", "secretKey": "reg.yaml"}
    )

    for template in await make_templates(values):
        if template["metadata"]["name"].startswith(f"{release_name}-synapse") and template["kind"] == "StatefulSet":
            for volume in template["spec"]["template"]["spec"]["volumes"]:
                if (
                    "secret" in volume
                    and volume["secret"]["secretName"] == f"as-{release_name}"
                    and volume["name"] == "as-0"
                ):
                    break
            else:
                raise AssertionError(
                    "The appservice secret wasn't included in the volumes : "
                    f"{','.join([volume['name'] for volume in template['spec']['template']['spec']['volumes']])}"
                )

            for volumeMount in template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]:
                if volumeMount["name"] == "as-0" and volumeMount["mountPath"] == "/as/0/reg.yaml":
                    break
            else:
                raise AssertionError("The appservice secret isn't mounted at the expected location")


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_max_upload_size_annotation_global_ingressType(values, make_templates):
    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "nginx.ingress.kubernetes.io/proxy-body-size" not in template["metadata"].get("annotations", {})

    values.setdefault("ingress", {})["controllerType"] = "ingress-nginx"

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "nginx.ingress.kubernetes.io/proxy-body-size" in template["metadata"].get("annotations", {})


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_max_upload_size_annotation_component_ingressType(values, deployables_details, make_templates):
    def set_ingress_type(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Ingress, {"controllerType": "ingress-nginx"})

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "nginx.ingress.kubernetes.io/proxy-body-size" not in template["metadata"].get("annotations", {})

    iterate_deployables_ingress_parts(deployables_details, set_ingress_type)

    for template in await make_templates(values):
        if template["kind"] == "Ingress":
            assert "nginx.ingress.kubernetes.io/proxy-body-size" in template["metadata"].get("annotations", {})


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_log_level_overrides(values, make_templates):
    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "synapse" in template["metadata"]["name"]
            and "log_config.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["log_config.yaml"])
            log_level = log_yaml["root"]["level"]
            loggers = log_yaml["loggers"]
            assert log_level == "INFO"
            assert loggers == {
                "synapse.storage.SQL": {"level": "INFO"},
            }
            break
    else:
        raise RuntimeError("Could not find log_config.yaml")

    values["synapse"]["logging"] = {
        "rootLevel": "WARNING",
        "levelOverrides": {"synapse.storage.SQL": "DEBUG", "synapse.over.value": "INFO"},
    }

    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "synapse" in template["metadata"]["name"]
            and "log_config.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["log_config.yaml"])
            log_level = log_yaml["root"]["level"]
            loggers = log_yaml["loggers"]
            assert log_level == "WARNING"
            assert loggers == {"synapse.storage.SQL": {"level": "DEBUG"}, "synapse.over.value": {"level": "INFO"}}
            break
    else:
        raise RuntimeError("Could not find log_config.yaml")


def assert_synapse_container(
    templates, template_to_deployable_details, assertion_visitor: Callable[[dict[str, Any], dict[str, Any]], None]
):
    for template in templates:
        if template_to_deployable_details(template).name != "synapse":
            continue

        if template["kind"] != "StatefulSet":
            continue

        for container in template["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "synapse":
                assertion_visitor(template, container)
                break
        else:
            raise AssertionError(f"{template_id(template)} has no container named 'synapse'")


@pytest.mark.parametrize("values_file", ["synapse-worker-example-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_synapse_resources_shared_by_default(values, make_templates, template_to_deployable_details):
    resources = {
        "requests": {
            "cpu": "1000",
            "memory": "2000Mi",
        },
        "limits": {
            "cpu": "3000",
            "memory": "4000Mi",
        },
    }
    values["synapse"]["resources"] = resources

    def assert_expected_resources(template, container):
        assert container["resources"] == resources, (
            f"{template_id(template)} has incorrect resources {container['resources']} vs {resources}"
        )

    assert_synapse_container(await make_templates(values), template_to_deployable_details, assert_expected_resources)


@pytest.mark.parametrize("values_file", ["synapse-worker-example-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_per_worker_synapse_resources(all_values, release_name, make_templates, template_to_deployable_details):
    workers_to_resources = {}
    counter = 1

    def set_resources(worker_name, values_fragment):
        nonlocal counter
        workers_to_resources[worker_name] = {
            "requests": {
                "cpu": f"{1000 + counter}",
                "memory": f"{2000 + counter}Mi",
            },
            "limits": {
                "cpu": f"{3000 + counter}",
                "memory": f"{4000 + counter}Mi",
            },
        }
        counter += 1
        values_fragment["resources"] = workers_to_resources[worker_name]

    iterate_synapse_workers_parts(all_values, set_resources)

    seen_workers = []

    def assert_expected_resources(template, container):
        worker_name = template["metadata"]["name"].replace(f"{release_name}-synapse-", "")
        if worker_name == "":
            worker_name = "main"
        seen_workers.append(worker_name)

        expected_resources = workers_to_resources[worker_name]
        assert container["resources"] == expected_resources, (
            f"{template_id(template)} has incorrect resources {container['resources']} vs {expected_resources}"
        )

    assert_synapse_container(
        await make_templates(all_values), template_to_deployable_details, assert_expected_resources
    )
    assert len(workers_to_resources) == len(seen_workers), f"{seen_workers} has not seen all the expected workers"
