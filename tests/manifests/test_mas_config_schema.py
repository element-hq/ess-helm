# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import json
from typing import Any

import aiohttp
import jsonschema
import pytest
import semver
import yaml

from . import secret_values_files_to_test, values_files_to_test
from .oci_helpers import get_oci_image_source_ref


def _make_strict(schema: dict[str, Any]) -> None:
    """Recursively add additionalProperties: false to every object sub-schema
    that has properties but no additionalProperties."""
    if not isinstance(schema, dict):
        return

    if "properties" in schema and "additionalProperties" not in schema:
        schema["additionalProperties"] = False

    for key in ("properties", "$defs", "definitions"):
        if key in schema and isinstance(schema[key], dict):
            for child in schema[key].values():
                _make_strict(child)

    if "items" in schema:
        _make_strict(schema["items"])

    for key in ("allOf", "anyOf", "oneOf"):
        if key in schema and isinstance(schema[key], list):
            for item in schema[key]:
                _make_strict(item)

    for key in ("if", "then", "else"):
        if key in schema:
            _make_strict(schema[key])


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Lists are replaced, not appended."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


async def fetch_mas_schema(ref):
    url = f"https://raw.githubusercontent.com/element-hq/matrix-authentication-service/{ref}/docs/config.schema.json"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession() as session, session.get(url, timeout=timeout) as resp:
        # There are edge case where we were not able to reliably map an
        # image tag to a git ref, in which case we're going to get a 404
        # from GitHub, and we'll skip the test
        if resp.status == 200:
            raw = await resp.read()
            return json.loads(raw)
    return {}


@pytest.fixture(scope="session")
async def strict_mas_schema(pytestconfig: pytest.Config, base_values: dict[str, Any]) -> dict[str, Any]:
    tag = base_values["matrixAuthenticationService"]["image"]["tag"]
    cacheable = False
    if tag.startswith("sha-"):
        # sha-xxyyzz → commit ref xxyyzz
        ref = tag.removeprefix("sha-")
        cacheable = True
    elif semver.Version.is_valid(tag):
        # 1.10.0 → tag v1.10.0
        ref = f"v{tag}"
        cacheable = True
    else:
        # main, or any other branch/tag name
        ref = tag

    cache_key = f"ess-helm/mas-config-schema/{ref}"
    cached = pytestconfig.cache.get(cache_key, None) if cacheable else None

    if cached is not None:
        schema = cached
    else:
        schema = await fetch_mas_schema(ref)
        if not schema:
            # In case of 404, it probably means we are targetting an image tag which does not match perfectly
            # to a git ref.
            # We have to parse the docker image attestations to find the proper ref
            source_ref = await get_oci_image_source_ref(base_values["matrixAuthenticationService"]["image"])
            schema = await fetch_mas_schema(source_ref)
        if not schema:
            pytest.fail(
                f"Failed to fetch schema for {base_values['matrixAuthenticationService']['image']['registry']}"
                f"/{base_values['matrixAuthenticationService']['image']['repository']}:{base_values['matrixAuthenticationService']['image']['tag']}"
            )
        if cacheable:
            pytestconfig.cache.set(cache_key, schema)

    strict = copy.deepcopy(schema)
    _make_strict(strict)

    # Remove top-level required to avoid false positives when a values file
    # doesn't enable Synapse (which supplies the 'matrix' section, etc.)
    strict.pop("required", None)

    return strict


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_mas_config_validates_against_strict_schema(templates, strict_mas_schema):
    mas_configmaps = [
        t
        for t in templates
        if t["kind"] == "ConfigMap"
        and "matrix-authentication-service" in t["metadata"]["name"]
        and "mas-config-overrides.yaml" in t.get("data", {})
    ]

    if not mas_configmaps:
        pytest.skip("MAS not enabled for this values file")

    for cm in mas_configmaps:
        cm_name = cm["metadata"]["name"]
        data = cm["data"]

        underrides_raw = data.get("mas-config-underrides.yaml", "{}")
        overrides_raw = data.get("mas-config-overrides.yaml", "{}")

        underrides = yaml.safe_load(underrides_raw) or {}
        overrides = yaml.safe_load(overrides_raw) or {}

        merged = _deep_merge(underrides, overrides)

        try:
            jsonschema.validate(instance=merged, schema=strict_mas_schema)
        except jsonschema.ValidationError as exc:
            path = ".".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "<root>"
            pytest.fail(f"ConfigMap {cm_name}: schema validation failed at '{path}': {exc.message}")
