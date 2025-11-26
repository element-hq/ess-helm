# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import DeployableDetails, PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id, template_to_deployable_details, workload_spec_containers


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pods_with_tags_and_no_digests(release_name, values, make_templates):
    counter = 1
    matrix_tools_marker = f"matrix-tools-marker={release_name}"
    values.setdefault("matrixTools", {}).setdefault("image", {}).update(
        {"repository": matrix_tools_marker, "tag": f"image-tag-{counter}", "digest": None}
    )

    def set_tag(deployable_details: DeployableDetails):
        nonlocal counter
        counter += 1
        deployable_details.set_helm_values(values, PropertyType.Image, {"tag": f"image-tag-{counter}", "digest": None})

    iterate_deployables_parts(set_tag, lambda deployable_details: deployable_details.has_image)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_image:
                expected_image_values = deployable_details.get_helm_values(values, PropertyType.Image)
            else:
                expected_image_values = values["matrixTools"]["image"]
            assert template["metadata"]["labels"]["app.kubernetes.io/version"] == expected_image_values["tag"], (
                f"{template_id(template)} doesn't have the expected version label on the parent"
            )

            pod_template = template["spec"]["template"]
            assert pod_template["metadata"]["labels"]["app.kubernetes.io/version"] == expected_image_values["tag"], (
                f"{template_id(template)} doesn't have the expected version label on the pod"
            )

            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert "image" in container, f"{template_id(template)} has container {container['name']} without image"

                deployable_details = template_to_deployable_details(template, container["name"])
                container_image = container["image"]
                if deployable_details.has_image and f"/{matrix_tools_marker}:" not in container_image:
                    expected_image_values = deployable_details.get_helm_values(values, PropertyType.Image)
                else:
                    expected_image_values = values["matrixTools"]["image"]

                assert expected_image_values["tag"] == container["image"].split(":")[1], (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image tag"
                )
                assert container["imagePullPolicy"] == "Always", (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image pull policy"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pods_with_digests_and_tags(release_name, values, make_templates):
    counter = 1
    matrix_tools_marker = f"matrix-tools-marker={release_name}"
    values.setdefault("matrixTools", {}).setdefault("image", {}).update(
        {
            "repository": matrix_tools_marker,
            "tag": f"image-tag-{counter}",
            "digest": f"sha256:digest{counter}",
        }
    )

    def set_tag(deployable_details: DeployableDetails):
        nonlocal counter
        counter += 1
        deployable_details.set_helm_values(
            values, PropertyType.Image, {"tag": f"image-tag-{counter}", "digest": f"sha256:digest{counter}"}
        )

    iterate_deployables_parts(set_tag, lambda deployable_details: deployable_details.has_image)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            deployable_details = template_to_deployable_details(template)
            if deployable_details.has_image:
                expected_image_values = deployable_details.get_helm_values(values, PropertyType.Image)
            else:
                expected_image_values = values["matrixTools"]["image"]
            assert template["metadata"]["labels"]["app.kubernetes.io/version"] == expected_image_values["tag"], (
                f"{template_id(template)} doesn't have the expected version label on the parent"
            )

            pod_template = template["spec"]["template"]
            assert pod_template["metadata"]["labels"]["app.kubernetes.io/version"] == expected_image_values["tag"], (
                f"{template_id(template)} doesn't have the expected version label on the pod"
            )

            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert "image" in container, f"{template_id(template)} has container {container['name']} without image"

                deployable_details = template_to_deployable_details(template, container["name"])
                container_image = container["image"]
                if deployable_details.has_image and f"/{matrix_tools_marker}@sha256" not in container_image:
                    expected_image_values = deployable_details.get_helm_values(values, PropertyType.Image)
                else:
                    expected_image_values = values["matrixTools"]["image"]

                assert expected_image_values["digest"] == container["image"].split("@")[1], (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image digest"
                )
                assert container["imagePullPolicy"] == "IfNotPresent", (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image pull policy"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pods_with_digest_and_no_tags(release_name, values, make_templates):
    counter = 1
    matrix_tools_marker = f"matrix-tools-marker={release_name}"
    values.setdefault("matrixTools", {}).setdefault("image", {}).update(
        {
            "repository": matrix_tools_marker,
            "tag": None,
            "digest": f"sha256:digest{counter}",
        }
    )

    def set_tag(deployable_details: DeployableDetails):
        nonlocal counter
        counter += 1
        deployable_details.set_helm_values(
            values, PropertyType.Image, {"tag": None, "digest": f"sha256:digest{counter}"}
        )

    iterate_deployables_parts(set_tag, lambda deployable_details: deployable_details.has_image)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            assert template["metadata"]["labels"]["app.kubernetes.io/version"] is None, (
                f"{template_id(template)} unexpectedly has a version label on the parent"
            )

            pod_template = template["spec"]["template"]
            assert pod_template["metadata"]["labels"]["app.kubernetes.io/version"] is None, (
                f"{template_id(template)} unexpectedly has a version label on the pod"
            )

            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert "image" in container, f"{template_id(template)} has container {container['name']} without image"

                deployable_details = template_to_deployable_details(template, container["name"])
                container_image = container["image"]
                if deployable_details.has_image and f"/{matrix_tools_marker}@sha256" not in container_image:
                    expected_image_values = deployable_details.get_helm_values(values, PropertyType.Image)
                else:
                    expected_image_values = values["matrixTools"]["image"]

                assert expected_image_values["digest"] == container["image"].split("@")[1], (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image digest"
                )
                assert container["imagePullPolicy"] == "IfNotPresent", (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image pull policy"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_global_pullPolicy_overrides_templateDefaults(values, make_templates):
    # We use `Never` as it isn't used as a default pullPolicy for tags or digests
    values.setdefault("image", {})["pullPolicy"] = "Never"
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert container["imagePullPolicy"] == "Never", (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image pull policy"
                )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_specific_image_pullPolicy_overrides_global_pullPolicy(values, make_templates):
    values.setdefault("image", {})["pullPolicy"] = "Always"

    # We use `Never` as it isn't used as a default pullPolicy for tags or digests
    values.setdefault("matrixTools", {}).setdefault("image", {})["pullPolicy"] = "Never"

    def set_pull_policy(deployable_details: DeployableDetails):
        deployable_details.set_helm_values(values, PropertyType.Image, {"pullPolicy": "Never"})

    iterate_deployables_parts(set_pull_policy, lambda deployable_details: deployable_details.has_image)
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            for container in workload_spec_containers(template["spec"]["template"]["spec"]):
                assert container["imagePullPolicy"] == "Never", (
                    f"{template_id(template)} has container {container['name']} "
                    "which doesn't have the expected image pull policy"
                )
