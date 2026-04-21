# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pyhelm3
import pytest


@pytest.mark.parametrize("values_file", ["matrix-authentication-service-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_env_overrides(values, make_templates):
    for template in await make_templates(values):
        if "matrix-authentication-service" in template["metadata"]["name"] and template["kind"] == "Deployment":
            env = {e["name"]: e["value"] for e in template["spec"]["template"]["spec"]["containers"][0]["env"]}
            assert env["MAS_CONFIG"] == "/conf/mas-config.yaml"
            break
    else:
        raise RuntimeError("Could not find Matrix Authentication Service deployment")

    values["matrixAuthenticationService"]["extraEnv"] = [
        {"name": "MAS_CONFIG", "value": "should-not-override"},
        {"name": "OTHER_KEY", "value": "should-exists"},
    ]

    for template in await make_templates(values):
        if "matrix-authentication-service" in template["metadata"]["name"] and template["kind"] == "Deployment":
            env = {e["name"]: e["value"] for e in template["spec"]["template"]["spec"]["containers"][0]["env"]}
            assert env["MAS_CONFIG"] == "/conf/mas-config.yaml"
            assert env["OTHER_KEY"] == "should-exists"
            break
    else:
        raise RuntimeError("Could not find Matrix Authentication Service deployment")


@pytest.mark.parametrize("values_file", ["matrix-authentication-service-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_invalid_yaml_in_matrix_authentication_service_additional_fails(values, make_templates):
    values["matrixAuthenticationService"]["additional"] = {"invalid.yaml": {"config": "not yaml"}}

    with pytest.raises(
        pyhelm3.errors.FailedToRenderChartError,
        match="matrixAuthenticationService.additional\\['invalid.yaml'\\] is invalid:",
    ):
        await make_templates(values)
