# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_matrix_tools_containers_dont_set_command(templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "StatefulSet", "Job"]:
            continue
        pod_spec = template["spec"]["template"]["spec"]
        for container in pod_spec.get("initContainers", []) + pod_spec["containers"]:
            if "/matrix-tools:" in container["image"] or "/matrix-tools@sha256:" in container["image"]:
                assert "command" not in container, (
                    f"{template_id(template)}/{container['name']} has a command of {container['command']}"
                )
