# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest


@pytest.mark.parametrize("values_file", ["matrix-authentication-service-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_matrix_authentication_service_env_overrides(values, make_templates):
    for template in await make_templates(values):
        if "matrix-authentication-service" in template["metadata"]["name"] and template["kind"] == "Deployment":
            env = {e["name"]: e["value"] for e in template["spec"]["template"]["spec"]["containers"][0]["env"]}
            assert env["MAS_CONFIG"] == "/config.yaml"
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
            assert env["MAS_CONFIG"] == "/config.yaml"
            assert env["OTHER_KEY"] == "should-exists"
            break
    else:
        raise RuntimeError("Could not find Matrix Authentication Service deployment")
