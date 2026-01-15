# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml
from frozendict import frozendict
from yaml.representer import Representer

from . import PropertyType, all_deployables_details, values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_nothing_enabled_renders_nothing(templates):
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_initSecrets_on_its_own_renders_nothing(values, make_templates):
    values.setdefault("initSecrets", {})["enabled"] = True
    templates = await make_templates(values)
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_postgres_on_its_own_renders_nothing(values, make_templates):
    values.setdefault("postgres", {})["enabled"] = True
    templates = await make_templates(values)
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_manifests_have_names_linked_to_deployables(release_name, templates):
    assert len(templates) > 0

    allowed_starts_with = []
    for deployable_details in all_deployables_details:
        allowed_starts_with.append(f"{release_name}-{deployable_details.name}")

    for template in templates:
        assert any(template["metadata"]["name"].startswith(allowed_start) for allowed_start in allowed_starts_with), (
            f"{template_id(template)} does not start with one of {allowed_starts_with}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_values_file_renders_idempotent(values, make_templates):
    first_render = {}
    for template in await make_templates(values, skip_cache=True):
        first_render[template_id(template)] = template
    second_render = {}
    for template in await make_templates(values, skip_cache=True):
        second_render[template_id(template)] = template

    assert set(first_render.keys()) == set(second_render.keys()), "Values file should render the same templates"
    for id in first_render:
        assert first_render[id] == second_render[id], f"Template {id} should be rendered the same twice"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_names_arent_too_long(templates):
    for template in templates:
        max_length = 63
        if template["kind"] == "StatefulSet":
            # https://github.com/kubernetes/kubernetes/issues/64023
            # https://github.com/kubernetes/kubernetes/pull/117507
            # Max of 63 - 1 for `-` - 10 for hash string
            max_length = 63 - 1 - 10

        assert len(template["metadata"]["name"]) <= max_length, (
            f"{template_id(template)} has a name that's too long. "
            f"Needs to be {len(template['metadata']['name']) - max_length} characters shorter"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_manifests_have_namespaces_correctly_set(templates, namespace):
    for template in templates:
        assert "namespace" in template["metadata"], f"{template_id(template)} doesn't specify a namespace"
        assert template["metadata"]["namespace"] == namespace, f"{template_id(template)} has set the wrong namespace"


@pytest.mark.asyncio_cooperative
async def test_default_values_file_sets_stub_values(base_values):
    # Tests that values.yaml has defaults (and thus almost certainly comments) for various properties
    # As we set additionalProperties: false almost everywhere this also implicitly asserts that the
    # field is in the schema.

    # We can't use None as get_helm_values replaces that with {}
    unset_marker = "XXXX unset XXX"
    for deployable_details in all_deployables_details:
        extraEnv = deployable_details.get_helm_values(base_values, PropertyType.Env, default_value=unset_marker)
        extraInitContainers = deployable_details.get_helm_values(
            base_values, PropertyType.InitContainers, default_value=unset_marker
        )
        nodeSelector = deployable_details.get_helm_values(
            base_values, PropertyType.NodeSelector, default_value=unset_marker
        )
        topologySpreadConstraints = deployable_details.get_helm_values(
            base_values, PropertyType.TopologySpreadConstraints, default_value=unset_marker
        )
        if deployable_details.has_workloads:
            assert extraEnv == [], f"{deployable_details.name} has default {extraEnv=} rather than []"
            # The below might be None iff a `not_supported` values file path override is set, e.g. for Sidecars
            # default_value=unset_marker means that an omitted property in the values file won't
            # return None here
            assert extraInitContainers == [] or extraInitContainers is None, (
                f"{deployable_details.name} has default {extraInitContainers=} rather than {{}}"
            )
            assert nodeSelector == {} or nodeSelector is None, (
                f"{deployable_details.name} has default {nodeSelector=} rather than {{}}"
            )
            assert topologySpreadConstraints == [] or topologySpreadConstraints is None, (
                f"{deployable_details.name} has default {topologySpreadConstraints=} rather than []"
            )
        else:
            assert extraEnv == unset_marker, (
                f"{deployable_details.name} has default {extraEnv=} rather than being unset"
            )
            assert extraInitContainers == unset_marker, (
                f"{deployable_details.name} has default {extraEnv=} rather than being unset"
            )
            assert nodeSelector == unset_marker, (
                f"{deployable_details.name} has default {nodeSelector=} rather than being unset"
            )
            assert topologySpreadConstraints == unset_marker, (
                f"{deployable_details.name} has default {topologySpreadConstraints=} rather than being unset"
            )

        hostAliases = deployable_details.get_helm_values(
            base_values, PropertyType.HostAliases, default_value=unset_marker
        )
        if deployable_details.makes_outbound_requests:
            assert hostAliases == [], f"{deployable_details.name} has default {hostAliases=} rather than []"
        else:
            assert hostAliases == unset_marker, (
                f"{deployable_details.name} has default {hostAliases=} rather than being unset"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_doesnt_contain_any_unrendered_helm_templates(templates):
    yaml.SafeDumper.add_representer(frozendict, Representer.represent_dict)
    # This test does not cover `NOTES.txt` as https://github.com/helm/helm/issues/6901
    for template in templates:
        for idx, line in enumerate(yaml.safe_dump(template).splitlines()):
            assert ".Values." not in line, (
                f"{template_id(template)} contains what looks like an un-rendered Helm template "
                f"on line number {idx + 1}"
            )
