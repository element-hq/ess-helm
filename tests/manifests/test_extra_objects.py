# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from manifests.utils import template_id


@pytest.mark.parametrize("values_file", ["extra-objects-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_extra_objects_are_templated(release_name, namespace, templates):
    assert len(templates) == 3, "There should be 3 extra objects rendered"

    for template in templates:
        assert template["metadata"]["namespace"] == namespace
        assert template["metadata"]["name"].startswith(release_name)
        if template["kind"] == "ConfigMap":
            assert template["metadata"]["labels"]["app.kubernetes.io/part-of"] == "matrix-stack"
        elif template["kind"] not in ["LimitRange", "ResourceQuota"]:
            raise AssertionError(f"Unexpected object rendered: {template_id(template)}")
