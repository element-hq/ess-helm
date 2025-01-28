# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

import pytest

from .fixtures import ESSData
from .lib.utils import aiottp_get_json, value_file_has


@pytest.mark.skipif(value_file_has("wellKnownDelegation.enabled", False), reason="WellKnownDelegation not deployed")
@pytest.mark.asyncio_cooperative
async def test_well_known_files_can_be_accessed(
    ingress_ready,
    ssl_context,
    generated_data: ESSData,
):
    await ingress_ready("well-known")

    json_content = await aiottp_get_json(f"https://{generated_data.server_name}/.well-known/matrix/client", ssl_context)
    if value_file_has("synapse.enabled", True):
        assert "m.homeserver" in json_content
    else:
        assert json_content == {}

    json_content = await aiottp_get_json(f"https://{generated_data.server_name}/.well-known/matrix/server", ssl_context)
    if value_file_has("synapse.enabled", True):
        assert "m.server" in json_content
    else:
        assert json_content == {}

    json_content = await aiottp_get_json(
        f"https://{generated_data.server_name}/.well-known/matrix/support", ssl_context
    )
    assert json_content == {}

    json_content = await aiottp_get_json(
        f"https://{generated_data.server_name}/.well-known/element/element.json", ssl_context
    )
    assert json_content == {}
