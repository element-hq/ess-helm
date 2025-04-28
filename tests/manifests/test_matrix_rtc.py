# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_log_level_overrides(values, deployables_details, make_templates):
    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "matrix-rtc-sfu" in template["metadata"]["name"]
            and "config.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["config.yaml"])
            use_external_ip = log_yaml["rtc"]["use_external_ip"]
            tcp_port = log_yaml["rtc"]["tcp_port"]
            assert type(use_external_ip) is bool and use_external_ip
            assert tcp_port == 30881
            break
    else:
        raise RuntimeError("Could not find config.yaml")

    values["matrixRTC"].setdefault("sfu", {})["additional"] = yaml.dump(
        {
            "rtc": {
                "use_external_ip": False,
                "tcp_port": 32001,
            },
        }
    )

    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "matrix-rtc-sfu" in template["metadata"]["name"]
            and "config.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["config.yaml"])
            use_external_ip = log_yaml["rtc"]["use_external_ip"]
            tcp_port = log_yaml["rtc"]["tcp_port"]
            assert type(use_external_ip) is bool and not use_external_ip
            assert tcp_port == 32001
            break
    else:
        raise RuntimeError("Could not find config.yaml")
