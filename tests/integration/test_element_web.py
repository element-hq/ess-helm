# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from .fixtures import ESSData
from .lib.utils import aiohttp_get_json, value_file_has


@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_web_can_access_config_json(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("element-web")

    json_content = await aiohttp_get_json(f"https://element.{generated_data.server_name}/config.json", {}, ssl_context)
    assert "some_key" in json_content
    assert json_content["some_key"]["some_value"] == f"https://test.{generated_data.server_name}"
