# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest


@pytest.mark.parametrize("values_file", ["synapse-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_postgres_env_overrides(values, deployables_details, make_templates):
    for template in await make_templates(values):
        if (
            "postgres" in template["metadata"]["name"]
            and template["kind"] == "StatefulSet"
        ):
            env = {e["name"]: e["value"] for e in template["spec"]["template"]["spec"]["containers"][0]["env"]}
            assert env["PGDATA"] == "/var/lib/postgres/data/pgdata"
            break
    else:
        raise RuntimeError("Could not find Postgres statefulset")

    values["postgres"]["extraEnv"] = [
        {"name": "PGDATA", "value": "should-not-override"},
    ]

    for template in await make_templates(values):
        if (
            "postgres" in template["metadata"]["name"]
            and template["kind"] == "StatefulSet"
        ):
            env = {e["name"]: e["value"] for e in template["spec"]["template"]["spec"]["containers"][0]["env"]}
            assert env["PGDATA"] == "/var/lib/postgres/data/pgdata"
            break
    else:
        raise RuntimeError("Could not find Postgres statefulset")
