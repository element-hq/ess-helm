# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import base64
import json
import re

import pytest
import yaml

from . import DeployableDetails, PropertyType, secret_values_files_to_test, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details


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


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_user_provided_inline_configs_change_hashes(values, make_templates):
    hashes_by_template_id = {}
    for template in await make_templates(values):
        # We always look for hashes even if the deployable in question doesn't support additional config
        # as it could have hashes from other components (e.g. well-known delegation puts a hash on HAProxy)
        id = template_id(template)
        hashes_by_template_id[id] = {}

        # We only need to save the top-level hash here as we have test_pod_spec_labels_are_consistent_with_parent_labels
        for label, value in template["metadata"]["labels"].items():
            if (
                re.match(r"^k8s.element.io/([a-z0-9-]+)-(config|secret)-hash$", label) is not None
                and label not in hashes_by_template_id[id]
            ):
                hashes_by_template_id[id][label] = value

        if template_to_deployable_details(template).has_additional_config and template["kind"] in [
            "Deployment",
            "StatefulSet",
            "Job",
        ]:
            assert len(hashes_by_template_id[id]) > 0, (
                f"{id} supports additional configuration but we haven't seen any hashes"
            )

    def set_user_provided_config(deployable_details: DeployableDetails):
        # siiiiigh Element Web and Well-Known delegation have the same schema as everything else
        # They only support in-line config and not externally refererenced and so are missing `config`.
        # This is probably because anything in their configs ends up publicly available anyway but it would
        # be nice if they supported referencing `ConfigMaps`.
        # Well-Known delegation also restricts to providing additional config to 3 files and doesn't support merging
        if deployable_details.name == "element-web":
            deployable_details.set_helm_values(values, PropertyType.AdditionalConfig, {"foo": "some additional config"})
        elif deployable_details.name == "well-known":
            deployable_details.set_helm_values(
                values, PropertyType.AdditionalConfig, {"client": "some additional config"}
            )
        else:
            deployable_details.set_helm_values(
                values, PropertyType.AdditionalConfig, {"foo": {"config": "some additional config"}}
            )

    iterate_deployables_parts(
        set_user_provided_config, lambda deployable_details: deployable_details.has_additional_config
    )

    should_see_some_hashes_changed = False
    has_any_hash_changed = False
    for template in await make_templates(values):
        if template_to_deployable_details(template).has_additional_config:
            should_see_some_hashes_changed = True

        id = template_id(template)
        hashes = hashes_by_template_id[id]

        # We only need to test the top-level hash here as we have test_pod_spec_labels_are_consistent_with_parent_labels
        for label, value in template["metadata"]["labels"].items():
            if re.match(r"^k8s.element.io/([a-z0-9-]+)-(config|secret)-hash$", label) is not None:
                assert label in hashes, (
                    f"{template_id(template)} has label {label} but this only appeared after we set additional config"
                )
                if value != hashes[label]:
                    has_any_hash_changed = True

    if should_see_some_hashes_changed:
        assert has_any_hash_changed, "No hashes changed after setting some additional config"
