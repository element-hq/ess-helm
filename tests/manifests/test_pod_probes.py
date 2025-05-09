# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_jobs(templates):
    for template in templates:
        if template["kind"] == "Job":
            for container in template["spec"]["template"]["spec"]["containers"]:
                assert "livenessProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a livenessProbe"
                )
                assert "readinessProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a readinessProbe"
                )
                assert "startupProbe" not in container, (
                    f"{template_id(template)} has container {container['name']} with a startupProbe"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_no_probes_for_initContainers(templates):
    for template in templates:
        if template["kind"] == ["Deployment", "StatefulSet"]:
            for init_container in template["spec"]["template"]["spec"].get("initContainers", []):
                assert "livenessProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a livenessProbe"
                )
                assert "readinessProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a readinessProbe"
                )
                assert "startupProbe" not in init_container, (
                    f"{template_id(template)} has initContainer {init_container['name']} with a startupProbe"
                )
