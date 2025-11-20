# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_hook_weight_is_specified_if_manifest_is_hook(templates):
    for template in templates:
        annotations = template["metadata"].get("annotations", {})

        if "helm.sh/hook" in annotations:
            # If you want to use hook-weight of 0 (the default), it should be explicit
            assert "helm.sh/hook-weight" in annotations, (
                f"{template_id(template)} is a hook ({annotations['helm.sh/hook']}) but doesn't set a hook weight"
            )
        else:
            assert "helm.sh/hook-weight" not in annotations, (
                f"{template_id(template)} is not a hook but has set a hook weight"
            )
            assert "helm.sh/hook-delete-policy" not in annotations, (
                f"{template_id(template)} is not a hook but has set a hook delete policy"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sets_both_install_upgrade_hooks(templates):
    for template in templates:
        annotations = template["metadata"].get("annotations", {})

        if "helm.sh/hook" not in annotations:
            continue

        hooks = annotations["helm.sh/hook"].split(",")
        assert len(hooks) == 2, f"{template_id(template)} set an unexpected number of hooks {','.join(hooks)}"
        assert ("pre-install" in hooks and "pre-upgrade" in hooks) or (
            "post-install" in hooks and "post-upgrade" in hooks
        ), f"{template_id(template)} didn't set both the install and upgrade hooks"
