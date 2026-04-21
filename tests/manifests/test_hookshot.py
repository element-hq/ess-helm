# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pyhelm3
import pytest


@pytest.mark.parametrize("values_file", ["hookshot-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_invalid_yaml_in_hookshot_additional_fails(values, make_templates):
    values["hookshot"]["additional"] = {"invalid.yaml": {"config": "not yaml"}}

    with pytest.raises(
        pyhelm3.errors.FailedToRenderChartError, match="hookshot.additional\\['invalid.yaml'\\] is invalid:"
    ):
        await make_templates(values)
