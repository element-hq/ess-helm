# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import secret_values_files_to_test, values_files_to_test
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


@pytest.mark.parametrize("values_file", secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_secret_generated_when_unneeded(release_name, values, make_templates):
    values["initSecrets"] = {"enabled": True}
    for template in await make_templates(values):
        if template["kind"] == "Job":
            assert template["metadata"]["name"] != f"{release_name}-init-secrets"
