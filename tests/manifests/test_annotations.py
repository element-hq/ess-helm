# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from . import values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_annotations_dont_contain_things_that_should_be_labels(templates):
    for template in templates:
        annotations = template["metadata"].get("annotations", {})
        our_annotations = [key for key in annotations if "k8s.element.io" in key]
        assert len(our_annotations) == 0, (
            f"{template_id(template)} has {our_annotations=}. "
            "We should consistently use labels for k8s.element.io things"
        )

        if template["kind"] in ["Deployment", "Job", "StatefulSet"]:
            pod_annotations = template["metadata"].get("annotations", {})
            our_pod_annotations = [key for key in pod_annotations if "k8s.element.io" in key]
            assert len(our_pod_annotations) == 0, (
                f"{template_id(template)} has {our_pod_annotations=} in its Pod spec. "
                "We should consistently use labels for k8s.element.io things"
            )
