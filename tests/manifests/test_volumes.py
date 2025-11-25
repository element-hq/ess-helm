# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import secret_values_files_to_test, values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_emptyDirs_are_memory(templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "Job", "StatefulSet"]:
            continue

        for volume in template["spec"]["template"]["spec"].get("volumes", []):
            if "emptyDir" not in volume:
                continue

            assert "medium" in volume["emptyDir"], (
                f"{template_id(template)} has emptyDir {volume['name']} but doesn't set the medium"
            )
            assert volume["emptyDir"]["medium"] == "Memory", (
                f"{template_id(template)} has emptyDir {volume['name']} that isn't Memory backed"
            )
