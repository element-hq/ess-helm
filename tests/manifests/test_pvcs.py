# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test
from .utils import template_to_deployable_details


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvcs_only_present_if_expected(templates):
    deployable_details_to_seen_pvcs = {}
    for template in templates:
        deployable_details = template_to_deployable_details(template)
        deployable_details_to_seen_pvcs.setdefault(deployable_details, False)
        if template["kind"] == "PersistentVolumeClaim":
            deployable_details_to_seen_pvcs[deployable_details] = True

    for deployable_details, seen_pvcs in deployable_details_to_seen_pvcs.items():
        assert seen_pvcs == deployable_details.has_storage, (
            f"{deployable_details.name}: {seen_pvcs=} when expecting {deployable_details.has_storage}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pvcs_marked_as_being_kept_on_helm_uninstall_by_default(templates):
    for template in templates:
        if template["kind"] == "PersistentVolumeClaim":
            assert "helm.sh/resource-policy" in template["metadata"]["annotations"]
            assert template["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"
