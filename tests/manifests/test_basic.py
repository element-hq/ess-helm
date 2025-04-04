# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_nothing_enabled_renders_nothing(templates):
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_initSecrets_on_its_own_renders_nothing(values, make_templates):
    values.setdefault("initSecrets", {})["enabled"] = True
    templates = await make_templates(values)
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", ["nothing-enabled-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_postgres_on_its_own_renders_nothing(values, make_templates):
    values.setdefault("postgres", {})["enabled"] = True
    templates = await make_templates(values)
    assert len(templates) == 0, f"{templates} were generated but none were expected"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_values_file_renders_only_itself(release_name, deployables_details, templates):
    assert len(templates) > 0

    allowed_starts_with = []
    for deployable_details in deployables_details:
        allowed_starts_with.append(f"{release_name}-{deployable_details.name}")

    for template in templates:
        assert any(template["metadata"]["name"].startswith(allowed_start) for allowed_start in allowed_starts_with), (
            f"{template_id(template)} does not start with one of {allowed_starts_with}"
        )
