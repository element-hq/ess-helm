# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_all_secrets_have_type(templates):
    for template in templates:
        if template["kind"] == "Secret":
            assert "type" in template, f"{template_id(template)} has not set the Secret type"
            assert template["type"] in ["Opaque"], (
                f"{template_id(template)} has an unexpected Secret type {template['type']}"
            )
