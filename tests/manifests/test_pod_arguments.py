# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import iterate_pod_template, workload_spec_containers


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_matrix_tools_containers_dont_set_command(templates):
    for pod_template_details in iterate_pod_template(templates):
        for container in workload_spec_containers(pod_template_details.pod_template["spec"]):
            if "/matrix-tools:" in container["image"] or "/matrix-tools@sha256:" in container["image"]:
                assert "command" not in container, (
                    f"{pod_template_details.manifest_id}/{container['name']} has a command of {container['command']}"
                )
