# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import values_files_to_test
from .utils import template_id, template_to_deployable_details


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
        assert len(hooks) == 2, f"{template_id(template)} set an unexpected number of hooks: {','.join(hooks)}"
        assert ("pre-install" in hooks and "pre-upgrade" in hooks) or (
            "post-install" in hooks and "post-upgrade" in hooks
        ), f"{template_id(template)} didn't set both the install and upgrade hook: {','.join(hooks)}"


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_hook_weights_are_well_known(templates):
    for template in templates:
        annotations = template["metadata"].get("annotations", {})

        if "helm.sh/hook-weight" not in annotations:
            continue

        # Manifest install order by hook weight.
        # The kind order of manifests within the same weight is not respected, despire being documented as doing so
        # - https://github.com/helm/helm/issues/12414
        # - https://github.com/helm/helm-www/pull/1520
        # As such the weights for Jobs are given below, and then weight for non-Jobs are -1
        #
        # PRE INSTALL/UPGRADE
        # -10: init secrets, pre-deployment markers
        #   0: config check, syn2mas actual migration
        #
        # NON-HOOKS
        #
        # POST INSTALL/UPGRADE
        #   0: syn2mas dry-run
        #  10: post-deployment markers
        hook_weight = int(annotations["helm.sh/hook-weight"])
        weight_adjustment = 0 if template["kind"] == "Job" else 1
        hook_weight += weight_adjustment
        assert hook_weight in [-10, 0, 10], f"{template_id(template)} had an unexpected hook weight"

        deployable_details = template_to_deployable_details(template)
        template_name = template["metadata"]["name"]
        if deployable_details.name == "deployment-markers":
            if template_name.endswith("-pre"):
                assert hook_weight == -10, f"{template_id(template)} should have a weight of {-10 - weight_adjustment}"
            else:
                assert hook_weight == 10, f"{template_id(template)} should have a weight of {10 - weight_adjustment}"
        elif deployable_details.name == "init-secrets":
            assert hook_weight == -10, f"{template_id(template)} should have a weight of {-10 - weight_adjustment}"
        else:
            assert hook_weight == 0, f"{template_id(template)} should have a weight of {0 - weight_adjustment}"
