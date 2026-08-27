# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from frozendict import frozendict

from . import values_files_to_test
from .utils import ALL_WORKLOAD_KINDS, PodTemplateDetails, template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_annotations_absent_or_non_empty(templates):
    for template in templates:
        if "annotations" in template["metadata"]:
            assert isinstance(template["metadata"]["annotations"], frozendict), (
                f"{template_id(template)} has top-level annotations that isn't a dictionary"
            )
            assert len(template["metadata"]["annotations"]) > 0, (
                f"{template_id(template)} has empty top-level annotations rather than being absent"
            )

        if template["kind"] in ALL_WORKLOAD_KINDS:
            pod_template_details = PodTemplateDetails(template)

            if "annotations" in pod_template_details.pod_template["metadata"]:
                pod_annotations = pod_template_details.pod_template["metadata"]["annotations"]
                assert isinstance(pod_annotations, frozendict), (
                    f"{template_id(template)} has pod annotations that isn't a dictionary"
                )
                assert len(pod_annotations) > 0, (
                    f"{template_id(template)} has empty pod annotations rather than being absent"
                )


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

        if template["kind"] in ALL_WORKLOAD_KINDS:
            pod_template_details = PodTemplateDetails(template)
            pod_annotations = pod_template_details.pod_template["metadata"].get("annotations", {})
            our_pod_annotations = [key for key in pod_annotations if "k8s.element.io" in key]
            assert len(our_pod_annotations) == 0, (
                f"{template_id(template)} has {our_pod_annotations=} in its Pod spec. "
                "We should consistently use labels for k8s.element.io things"
            )
