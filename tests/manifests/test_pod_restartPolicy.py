# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import EPHEMERAL_WORKLOAD_KINDS, iterate_pod_template


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_restartPolicy_set_based_on_controller(templates):
    for pod_template_details in iterate_pod_template(templates):
        pod_spec = pod_template_details.pod_template["spec"]
        assert "restartPolicy" in pod_spec, f"{pod_template_details.manifest_id} doesn't set a Pod-level restartPolicy"
        if pod_template_details.manifest["kind"] in EPHEMERAL_WORKLOAD_KINDS:
            assert pod_spec["restartPolicy"] == "Never", (
                f"{pod_template_details.manifest_id} doesn't reset the Pod-level restartPolicy to 'Never' "
                "so failed Pods won't be kept around"
            )
        else:
            assert pod_spec["restartPolicy"] == "Always", (
                f"{pod_template_details.manifest_id} doesn't reset the Pod-level restartPolicy to 'Always'"
            )
