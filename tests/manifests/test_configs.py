# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import base64
import json

import pytest
import yaml

from . import secret_values_files_to_test


@pytest.mark.parametrize("values_file", secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_configs_are_valid(templates):
    for template in templates:
        if template["kind"] not in ["ConfigMap", "Secret"]:
            continue

        if "data" not in template or not template["data"]:
            continue
        for key, value in template["data"].items():
            if template["kind"] == "Secret":
                value = base64.b64decode(value)

            if key.endswith(".yaml") or key.endswith(".yml"):
                assert yaml.safe_load(value) is not None
            elif key.endswith(".json"):
                assert json.loads(value) is not None
