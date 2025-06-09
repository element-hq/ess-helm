# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import yaml


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_log_level_overrides(values, make_templates):
    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "matrix-rtc-sfu" in template["metadata"]["name"]
            and "config-overrides.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["config-overrides.yaml"])
            tcp_port = log_yaml["rtc"]["tcp_port"]
            assert tcp_port == 30881
            break
    else:
        raise RuntimeError("Could not find config.yaml")


@pytest.mark.parametrize("values_file", ["matrix-rtc-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_external_ip_underrides(values, make_templates):
    for template in await make_templates(values):
        if (
            template["kind"] == "ConfigMap"
            and "matrix-rtc-sfu" in template["metadata"]["name"]
            and "config-underrides.yaml" in template["data"]
        ):
            log_yaml = yaml.safe_load(template["data"]["config-underrides.yaml"])
            use_external_ip = log_yaml["rtc"]["use_external_ip"]
            assert type(use_external_ip) is bool
            assert use_external_ip
            break
    else:
        raise RuntimeError("Could not find config.yaml")
