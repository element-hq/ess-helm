# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_restartPolicy_set_based_on_controller(templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "StatefulSet", "Job"]:
            continue

        assert "restartPolicy" in template["spec"]["template"]["spec"], (
            f"{template_id(template)} doesn't set a Pod-level restartPolicy"
        )
        if template["kind"] == "Job":
            assert template["spec"]["template"]["spec"]["restartPolicy"] == "Never", (
                f"{template_id(template)} doesn't reset the Pod-level restartPolicy to 'Never' "
                "so failed Pods won't be kept around"
            )
        else:
            assert template["spec"]["template"]["spec"]["restartPolicy"] == "Always", (
                f"{template_id(template)} doesn't reset the Pod-level restartPolicy to 'Always'"
            )
