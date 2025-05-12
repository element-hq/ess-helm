# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import json
import random
import shutil
import string
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

import pyhelm3
import pytest
import yaml

from . import DeployableDetails, values_files_to_deployables_details

template_cache = {}
values_cache = {}


@pytest.fixture(scope="session")
async def release_name():
    return f"pytest-{''.join(random.choices(string.ascii_lowercase, k=6))}"


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


@pytest.fixture
def deployables_details(values_file) -> tuple[DeployableDetails, ...]:
    return values_files_to_deployables_details[values_file]


@pytest.fixture(scope="session")
def base_values() -> dict[str, Any]:
    return yaml.safe_load(Path("charts/matrix-stack/values.yaml").read_text("utf-8"))


@pytest.fixture
def values(values_file) -> dict[str, Any]:
    if values_file not in values_cache:
        v = yaml.safe_load((Path("charts/matrix-stack/ci") / values_file).read_text("utf-8"))
        if not v.get("initSecrets"):
            v["initSecrets"] = {"enabled": True}
        if not v.get("postgres"):
            v["postgres"] = {"enabled": True}
        if not v.get("wellKnownDelegation"):
            v["wellKnownDelegation"] = {"enabled": True}

        values_cache[values_file] = v
    return copy.deepcopy(values_cache[values_file])


@pytest.fixture
def all_values(values, base_values) -> dict[str, Any]:
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

    return merge(copy.deepcopy(base_values), copy.deepcopy(values))


@pytest.fixture
async def templates(chart: pyhelm3.Chart, release_name: str, values: dict[str, Any]):
    return await helm_template(chart, release_name, values)


@pytest.fixture
def other_secrets(release_name, values, templates):
    return list(generated_secrets(release_name, values, templates)) + list(external_secrets(release_name, values))


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

        command_line: list[str] = (
            init_secrets_job.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [{}])[0]
            .get("command", {})
        )
        assert len(command_line) == 6, "Unexpected command line in the init-secrets job"
        assert command_line[2] == "-secrets", "Can't find the secrets args for the init-secrets job"
        assert command_line[4] == "-labels", "Can't find the labels args for the init-secrets job"

        requested_secrets = command_line[3].split(",")
        requested_labels = {label.split("=")[0]: label.split("=")[1] for label in command_line[5].split(",")}
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
                        # but this is necessary for tests/manifests/test_configs_and_mounts_consistency.py
                        "helm.sh/hook-weight": "-9"
                    },
                },
                "data": {
                    secret_key: "".join(random.choices(string.ascii_lowercase, k=10)) for secret_key in secret_keys
                },
            }


def external_secrets(release_name, values):
    def find_credential(values_fragment):
        if isinstance(values_fragment, (dict, list)):
            for value in values_fragment.values() if isinstance(values_fragment, dict) else values_fragment:
                if isinstance(value, dict):
                    if "secret" in value and "secretKey" in value and len(value) == 2:
                        yield (value["secret"].replace("{{ $.Release.Name }}", release_name), value["secretKey"])
                    # We don't care about credentials in the Helm values as those will
                    # be added to the Secret generated by the chart and won't be external
                    else:
                        yield from find_credential(value)
                elif isinstance(value, list):
                    yield from find_credential(value)

    external_secrets_to_keys = {}
    for secret_name, secretKey in find_credential(values):
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
                    # but this is necessary for tests/manifests/test_configs_and_mounts_consistency.py
                    "helm.sh/hook-weight": "-100"
                },
            },
            "data": {secret_key: "".join(random.choices(string.ascii_lowercase, k=10)) for secret_key in secret_keys},
        }


async def helm_template(
    chart: pyhelm3.Chart, release_name: str, values: Any | None, has_service_monitor_crd=True, skip_cache=False
) -> list[Any]:
    """Generate template with ServiceMonitor API Versions enabled

    The native pyhelm3 template command does expose the --api-versions flag,
    so we implement it here.
    """
    additional_apis: list[str] = []
    if has_service_monitor_crd:
        additional_apis.append("monitoring.coreos.com/v1/ServiceMonitor")

    additional_apis_args = [arg for additional_api in additional_apis for arg in ["-a", additional_api]]
    command = [
        "template",
        release_name,
        str(chart.ref),
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
        templates = list(
            [
                template
                for template in yaml.load_all(
                    await pyhelm3.Command().run(command, json.dumps(values or {}).encode()), Loader=yaml.SafeLoader
                )
                if template is not None
            ]
        )
        template_cache[template_cache_key] = templates
    return template_cache[template_cache_key]


@pytest.fixture
def make_templates(chart: pyhelm3.Chart, release_name: str):
    async def _make_templates(values, has_service_monitor_crd=True, skip_cache=False):
        return await helm_template(chart, release_name, values, has_service_monitor_crd, skip_cache)

    return _make_templates


def iterate_deployables_parts(
    deployables_details: tuple[DeployableDetails],
    visitor: Callable[[DeployableDetails], None],
    if_condition: Callable[[DeployableDetails], bool],
):
    for deployable_details in deployables_details:
        if if_condition(deployable_details):
            visitor(deployable_details)


def iterate_deployables_workload_parts(
    deployables_details: tuple[DeployableDetails],
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(deployables_details, visitor, lambda deployable_details: deployable_details.has_workloads)


def iterate_deployables_image_parts(
    deployables_details: tuple[DeployableDetails],
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(deployables_details, visitor, lambda deployable_details: deployable_details.has_image)


def iterate_deployables_ingress_parts(
    deployables_details: tuple[DeployableDetails],
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(deployables_details, visitor, lambda deployable_details: deployable_details.has_ingress)


def iterate_deployables_service_monitor_parts(
    deployables_details: tuple[DeployableDetails],
    visitor: Callable[[DeployableDetails], None],
):
    iterate_deployables_parts(
        deployables_details, visitor, lambda deployable_details: deployable_details.has_service_monitor
    )


def iterate_synapse_workers_parts(
    all_values: dict[str, Any],
    visitor: Callable[[str, dict[str, Any]], None],
    key_to_check: str | None = None,
) -> None:
    if not all_values["synapse"]["enabled"]:
        return

    if key_to_check is None or key_to_check in all_values["synapse"]:
        visitor("main", all_values["synapse"])

    for worker_name, worker_values in all_values["synapse"]["workers"].items():
        if not worker_values["enabled"]:
            continue
        if key_to_check is None or key_to_check in worker_values:
            visitor(worker_name, worker_values)


@pytest.fixture
def template_to_deployable_details(deployables_details: tuple[DeployableDetails]):
    def _template_to_deployable_details(template: dict[str, Any]) -> DeployableDetails:
        # As per test_labels this doesn't have the release_name prefixed to it
        manifest_name: str = template["metadata"]["labels"]["app.kubernetes.io/name"]

        match = None
        for deployable_details in deployables_details:
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
        return match

    return _template_to_deployable_details


def template_id(template: dict[str, Any]) -> str:
    return f"{template['kind']}/{template['metadata']['name']}"


def get_or_empty(d, key):
    res = d.get(key, {})
    if res is not None:
        return res
    else:
        return {}
