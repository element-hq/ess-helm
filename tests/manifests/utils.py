# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import base64
import copy
import json
import random
import shutil
import string
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pyhelm3
import pytest
import yaml
from frozendict import deepfreeze, frozendict

from . import DeployableDetails, PropertyType, all_deployables_details

template_cache = {}
manifests_cache: dict[int, frozendict] = {}
values_cache = {}


@pytest.fixture(scope="session")
async def release_name():
    # As per test_names_arent_too_long we've only got 52 chars to play with
    # We give most (29) to the release_name (user controlled)
    # 'pytest-' is 7 chars, we need another 22 to get to 29.
    return f"pytest-{''.join(random.choices(string.ascii_lowercase, k=22))}"


@pytest.fixture(scope="session")
async def namespace():
    return f"pytest-{''.join(random.choices(string.ascii_lowercase, k=10))}"


@pytest.fixture(scope="session")
async def helm_client():
    return pyhelm3.Client()


@pytest.fixture
async def temp_chart(helm_client):
    with tempfile.TemporaryDirectory() as tmpdirname:
        shutil.copytree("charts/matrix-stack", Path(tmpdirname) / "matrix-stack")
        yield Path(tmpdirname) / "matrix-stack"


@pytest.fixture(scope="session")
async def chart(helm_client: pyhelm3.Client):
    return await helm_client.get_chart("charts/matrix-stack")


@pytest.fixture(scope="session")
def base_values() -> dict[str, Any]:
    return yaml.safe_load(Path("charts/matrix-stack/values.yaml").read_text("utf-8"))


@pytest.fixture
def values(values_file) -> dict[str, Any]:
    if (Path("charts/matrix-stack/ci") / values_file).exists():
        values_file_path = Path("charts/matrix-stack/ci") / values_file
    elif (Path("charts/matrix-stack/ci_extra") / values_file).exists():
        values_file_path = Path("charts/matrix-stack/ci_extra") / values_file
    else:
        raise FileNotFoundError(f"Could not find {values_file} in charts/matrix-stack")
    if values_file not in values_cache:
        v = yaml.safe_load((values_file_path).read_text("utf-8"))
        for default_enabled_component in [
            "elementAdmin",
            "elementWeb",
            "initSecrets",
            "postgres",
            "matrixRTC",
            "matrixAuthenticationService",
            "synapse",
            "wellKnownDelegation",
        ]:
            if default_enabled_component not in v:
                v[default_enabled_component] = {}
            if "enabled" not in v[default_enabled_component]:
                v[default_enabled_component]["enabled"] = True

        values_cache[values_file] = v
    return copy.deepcopy(values_cache[values_file])


@pytest.fixture
async def templates(chart: pyhelm3.Chart, release_name: str, namespace: str, values: dict[str, Any]):
    return await helm_template(chart, release_name, namespace, values)


@pytest.fixture
def other_secrets(release_name, values, templates):
    return list(generated_secrets(release_name, values, templates)) + list(external_secrets(release_name, values))


@pytest.fixture
def other_configmaps(release_name, values):
    return list(external_configmaps(release_name, values))


def generated_secrets(release_name: str, values: dict[str, Any], helm_generated_templates: list[Any]) -> Iterator[Any]:
    if values["initSecrets"]["enabled"]:
        init_secrets_job = None
        for template in helm_generated_templates:
            if template["kind"] == "Job" and template["metadata"]["name"] == f"{release_name}-init-secrets":
                init_secrets_job = template
                break
        else:
            # We don't have an init-secrets job
            return

        container = init_secrets_job.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])[0]
        args: list[str] = container.get("args") or container["command"][1:]
        assert len(args) == 5, "Unexpected args in the init-secrets job"
        assert args[1] == "-secrets", "Can't find the secrets args for the init-secrets job"
        assert args[3] == "-labels", "Can't find the labels args for the init-secrets job"

        requested_secrets = args[2].split(",")
        requested_labels = {label.split("=")[0]: label.split("=")[1] for label in args[4].split(",")}
        generated_secrets_to_keys: dict[str, list[str]] = {}
        for requested_secret in requested_secrets:
            secret_parts = requested_secret.split(":")
            generated_secrets_to_keys.setdefault(secret_parts[0], []).append(secret_parts[1])

        for secret_name, secret_keys in generated_secrets_to_keys.items():
            yield {
                "kind": "Secret",
                "metadata": {
                    "name": secret_name,
                    "labels": requested_labels,
                    "annotations": {
                        # We simulate the fact that it exists after initSecret
                        # using the hook weight.
                        # Actually it does not have any
                        # but this is necessary for tests/manifests/test_configs_consistency.py
                        "helm.sh/hook-weight": "-9"
                    },
                },
                "data": {
                    secret_key: base64.b64encode(
                        "".join(random.choices(string.ascii_lowercase, k=10)).encode("utf-8")
                    ).decode("utf-8")
                    for secret_key in secret_keys
                },
            }


def external_secrets(release_name, values):
    def find_credential(values_fragment):
        if isinstance(values_fragment, (dict, list)):
            for value in values_fragment.values() if isinstance(values_fragment, dict) else values_fragment:
                if isinstance(value, dict):
                    if "secret" in value and "secretKey" in value and len(value) == 2:
                        yield (value["secret"].replace("{{ $.Release.Name }}", release_name), value["secretKey"])
                    elif "configSecret" in value and "configSecretKey" in value and len(value) == 2:
                        yield (
                            value["configSecret"].replace("{{ $.Release.Name }}", release_name),
                            value["configSecretKey"],
                        )
                    # We don't care about credentials in the Helm values as those will
                    # be added to the Secret generated by the chart and won't be external
                    else:
                        yield from find_credential(value)
                elif isinstance(value, list):
                    yield from find_credential(value)

    def find_tlsSecret(values_fragment):
        if isinstance(values_fragment, (dict, list)):
            for k, v in values_fragment.items() if isinstance(values_fragment, dict) else values_fragment:
                if k == "tlsSecret":
                    yield v.replace("{{ $.Release.Name }}", release_name), "tls.crt"
                    yield v.replace("{{ $.Release.Name }}", release_name), "tls.key"
                elif isinstance(v, (dict, list)):
                    yield from find_tlsSecret(v)

    external_secrets_to_keys = {}
    for secret_name, secretKey in find_credential(values):
        external_secrets_to_keys.setdefault(secret_name, []).append(secretKey)

    for secret_name, secretKey in find_tlsSecret(values):
        external_secrets_to_keys.setdefault(secret_name, []).append(secretKey)

    for secret_name, secret_keys in external_secrets_to_keys.items():
        yield {
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "annotations": {
                    # We simulate the fact that it exists before the chart deployment
                    # using the hook weight.
                    # Actually it does not have any
                    # but this is necessary for tests/manifests/test_configs_consistency.py
                    "helm.sh/hook-weight": "-100"
                },
            },
            "data": {
                secret_key: base64.b64encode(
                    "".join(random.choices(string.ascii_lowercase, k=10)).encode("utf-8")
                ).decode("utf-8")
                for secret_key in secret_keys
            },
        }


def external_configmaps(release_name, values):
    def find_extra_configmaps(values_fragment):
        if isinstance(values_fragment, (dict, list)):
            for value in values_fragment.values() if isinstance(values_fragment, dict) else values_fragment:
                if isinstance(value, dict):
                    if "extraVolumes" in value:
                        for vol in value["extraVolumes"]:
                            if "configMap" in vol:
                                yield vol["configMap"]["name"].replace("{{ $.Release.Name }}", release_name)
                elif isinstance(value, list):
                    yield from find_extra_configmaps(value)

    for cm_name in find_extra_configmaps(values):
        yield {
            "kind": "ConfigMap",
            "metadata": {
                "name": cm_name,
                "annotations": {
                    # We simulate the fact that it exists before the chart deployment
                    # using the hook weight.
                    # Actually it does not have any
                    # but this is necessary for tests/manifests/test_configs_and_mounts_consistency.py
                    "helm.sh/hook-weight": "-100"
                },
            },
            "data": {},
        }


async def helm_template(
    chart: pyhelm3.Chart,
    release_name: str,
    namespace: str,
    values: Any | None,
    has_cert_manager_crd=True,
    has_service_monitor_crd=True,
    skip_cache=False,
) -> list[Any]:
    """Generate template with ServiceMonitor API Versions enabled

    The native pyhelm3 template command does expose the --api-versions flag,
    so we implement it here.
    """
    additional_apis: list[str] = []
    if has_service_monitor_crd:
        additional_apis.append("monitoring.coreos.com/v1/ServiceMonitor")

    if has_cert_manager_crd:
        additional_apis.append("cert-manager.io/v1/Certificate")

    additional_apis_args = [arg for additional_api in additional_apis for arg in ["-a", additional_api]]
    command = [
        "template",
        release_name,
        str(chart.ref),
        "--namespace",
        namespace,
        # We send the values in on stdin
        "--values",
        "-",
    ] + additional_apis_args

    template_cache_key = json.dumps(
        {
            "values": values,
            "additional_apis": additional_apis,
            "release_name": release_name,
        }
    )

    if skip_cache or template_cache_key not in template_cache:
        templates = []
        for template in yaml.load_all(
            await pyhelm3.Command().run(command, json.dumps(values or {}).encode()), Loader=yaml.SafeLoader
        ):
            if template:
                frozen_template = deepfreeze(template)
                manifests_cache.setdefault(hash(frozen_template), frozen_template)
                templates.append(manifests_cache[hash(frozen_template)])
        template_cache[template_cache_key] = templates
    return template_cache[template_cache_key]


@pytest.fixture
def make_templates(chart: pyhelm3.Chart, release_name: str, namespace: str):
    async def _make_templates(values, has_cert_manager_crd=True, has_service_monitor_crd=True, skip_cache=False):
        return await helm_template(
            chart, release_name, namespace, values, has_cert_manager_crd, has_service_monitor_crd, skip_cache
        )

    return _make_templates


def iterate_deployables_parts(
    visitor: Callable[[DeployableDetails], None],
    if_condition: Callable[[DeployableDetails], bool],
):
    for deployable_details in all_deployables_details:
        if if_condition(deployable_details):
            visitor(deployable_details)


def iterate_deployables_workload_parts(
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(visitor, lambda deployable_details: deployable_details.has_workloads)


def iterate_deployables_ingress_parts(
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(visitor, lambda deployable_details: deployable_details.has_ingress)


def template_to_deployable_details(template: dict[str, Any], container_name: str | None = None) -> DeployableDetails:
    # As per test_labels this doesn't have the release_name prefixed to it
    manifest_name: str = template["metadata"]["labels"]["app.kubernetes.io/name"]

    match = None
    for deployable_details in all_deployables_details:
        # We name the various DeployableDetails to match the name the chart should use for
        # the manifest name and thus the app.kubernetes.io/name label above. e.g. A manifest
        # belonging to Synapse should be named `<release-name>-synapse(-<optional extra>)`.
        #
        # When we find a matching (sub-)component we ensure that there has been no other
        # match (with the exception of matching both a sub-component and its parent) as
        # otherwise we have no way of identifying the associated DeployableDeploys and
        # thus which parts of the values files need manipulating for this deployable.
        if deployable_details.owns_manifest_named(manifest_name):
            assert match is None, (
                f"{template_id(template)} could belong to at least 2 (sub-)components: "
                f"{match.name} and {deployable_details.name}"  # type: ignore[attr-defined]
            )
            match = deployable_details

    assert match is not None, f"{template_id(template)} can't be linked to any (sub-)component"
    # If this is a template that has multiple containers, the containers could have different ownership
    # e.g. a sidecar. For everything else we don't need to check further as there's no shared ownership
    if container_name is not None:
        match = match.deployable_details_for_container(container_name)
        assert match is not None, (
            f"{template_id(template)} can't be linked to any (sub-)component or specific container"
        )
    return match


def template_id(template: dict[str, Any]) -> str:
    return f"{template['kind']}/{template['metadata']['name']}"


def get_or_empty(d, key):
    res = d.get(key, {})
    if res is not None:
        return res
    else:
        return {}


def find_workload_ids_matching_selector(templates: list[dict[str, Any]], selector: dict[str, str]) -> set[str]:
    workload_ids = set[str]()
    for template in templates:
        if template["kind"] in ("Deployment", "StatefulSet", "Job") and selector_match(
            template["spec"]["template"]["metadata"]["labels"], selector
        ):
            workload_ids.add(template_id(template))

    return workload_ids


def find_services_matching_selector(templates: list[dict[str, Any]], selector: dict[str, str]) -> list[dict[str, Any]]:
    services = []
    for template in templates:
        if template["kind"] == "Service" and selector_match(template["metadata"]["labels"], selector):
            services.append(template)
    return services


def selector_match(labels: dict[str, str], selector: dict[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in selector.items())


async def assert_covers_expected_workloads(
    values,
    make_templates,
    covering_kind: str,
    toggling_property_type: PropertyType,
    if_condition: Callable[[DeployableDetails], bool],
    workload_ids_covered_by_template: Callable[[dict[str, Any], dict[str, list[dict[str, Any]]]], set[str]],
):
    def disable_covering_templates(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, toggling_property_type, {"enabled": False})

    iterate_deployables_parts(disable_covering_templates, if_condition)

    # We should now have no rendered templates of the covering_kind
    workload_ids_to_cover = set()
    for template in await make_templates(values):
        assert template["kind"] != covering_kind, (
            f"{template_id(template)} unexpectedly exists when all {covering_kind} should be turned off"
        )
        deployable_details = template_to_deployable_details(template)
        if template["kind"] in ["Deployment", "StatefulSet"] and if_condition(deployable_details):
            workload_ids_to_cover.add(template_id(template))

    def enable_covering_templates(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, toggling_property_type, {"enabled": True})

    iterate_deployables_parts(enable_covering_templates, if_condition)

    templates_by_kind = dict[str, list[dict[str, Any]]]()
    for template in await make_templates(values):
        templates_by_kind.setdefault(template["kind"], []).append(template)

    covered_workload_ids = set[str]()
    for seen_covering_template in templates_by_kind.get(covering_kind, []):
        new_covered_workload_ids = workload_ids_covered_by_template(seen_covering_template, templates_by_kind)
        assert len(new_covered_workload_ids) > 0, f"{template_id(seen_covering_template)} should cover some workloads"

        assert all(
            [
                covered_workload_id.split("/")[1].startswith(seen_covering_template["metadata"]["name"])
                for covered_workload_id in new_covered_workload_ids
            ]
        ), (
            f"{template_id(seen_covering_template)}'s name isn't a prefix of/the same as all the workloads"
            f" it covers: {new_covered_workload_ids}"
        )

        assert covered_workload_ids.intersection(new_covered_workload_ids) == set(), (
            "Workloads were covered more than once"
        )
        covered_workload_ids.update(new_covered_workload_ids)

    assert workload_ids_to_cover == covered_workload_ids, "Not all workloads we were expecting to cover were covered"


def workload_spec_containers(workload_spec):
    for container in workload_spec.get("initContainers", []):
        yield container
    for container in workload_spec.get("containers", []):
        yield container
