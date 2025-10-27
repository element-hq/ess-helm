# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import PropertyType, values_files_to_test
from .utils import iterate_deployables_parts, template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_sets_global_pull_secrets(values, make_templates):
    values.setdefault("image", {})["pullSecrets"] = [
        {"name": "global-secret"},
    ]
    values["imagePullSecrets"] = [
        {"name": "global-secret2"},
    ]
    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            assert "imagePullSecrets" in template["spec"]["template"]["spec"], f"{id} should have an imagePullSecrets"
            assert len(template["spec"]["template"]["spec"]["imagePullSecrets"]) == 2, (
                f"Expected {template_id(template)} to have 2 image pull secrets"
            )
            assert template["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] == "global-secret", (
                f"Expected {template_id(template)} to have image pull secret "
                f"'{values['image']['pullSecrets'][0]['name']}'"
            )
            assert template["spec"]["template"]["spec"]["imagePullSecrets"][1]["name"] == "global-secret2", (
                f"Expected {template_id(template)} to have image pull secret '{values['imagePullSecrets'][0]['name']}'"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_local_pull_secrets(values, base_values, make_templates):
    values.setdefault("image", {})["pullSecrets"] = [
        {"name": "global-secret"},
    ]
    values["imagePullSecrets"] = [
        {"name": "global-secret2"},
    ]
    values.setdefault("matrixTools", {}).setdefault("image", {})["pullSecrets"] = [{"name": "matrix-tools-secret"}]
    iterate_deployables_parts(
        lambda deployable_details: deployable_details.set_helm_values(
            values, PropertyType.Image, {"pullSecrets": [{"name": "local-secret"}]}
        ),
        lambda deployable_details: deployable_details.has_image,
    )

    for template in await make_templates(values):
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            any_container_uses_matrix_tools_image = any(
                [
                    base_values["matrixTools"]["image"]["repository"] in x["image"]
                    for x in (
                        template["spec"]["template"]["spec"]["containers"]
                        + template["spec"]["template"]["spec"].get("initContainers", [])
                    )
                ]
            )
            containers_with_matrix_tools_image = [
                base_values["matrixTools"]["image"]["repository"] in x["image"]
                for x in (
                    template["spec"]["template"]["spec"]["containers"]
                    + template["spec"]["template"]["spec"].get("initContainers", [])
                )
            ]
            any_container_uses_matrix_tools_image = any(containers_with_matrix_tools_image)
            containers_only_uses_matrix_tools_image = all(containers_with_matrix_tools_image)

            id = template_id(template)
            assert "imagePullSecrets" in template["spec"]["template"]["spec"], f"{id} should have an imagePullSecrets"

            secret_names = [x["name"] for x in template["spec"]["template"]["spec"]["imagePullSecrets"]]
            if containers_only_uses_matrix_tools_image:
                assert len(template["spec"]["template"]["spec"]["imagePullSecrets"]) == 3, (
                    f"Expected {id} to have 3 image pull secrets"
                )
                assert set(secret_names) == set(["matrix-tools-secret", "global-secret", "global-secret2"]), (
                    f"Expected {id} to have image pull secret names: local-secret, global-secret, global-secret2, "
                    f"got {','.join(secret_names)}"
                )

            elif any_container_uses_matrix_tools_image:
                assert len(template["spec"]["template"]["spec"]["imagePullSecrets"]) == 4, (
                    f"Expected {id} to have 4 image pull secrets"
                )

                assert set(secret_names) == set(
                    ["matrix-tools-secret", "local-secret", "global-secret", "global-secret2"]
                ), (
                    f"Expected {id} to have image pull secret names: "
                    f"local-secret, global-secret, global-secret2, matrix-tools-secret, got {','.join(secret_names)}"
                )
            else:
                assert len(template["spec"]["template"]["spec"]["imagePullSecrets"]) == 3, (
                    f"Expected {id} to have 3 image pull secrets"
                )
                assert set(secret_names) == set(["local-secret", "global-secret", "global-secret2"]), (
                    f"Expected {id} to have image pull secret names: local-secret, global-secret, global-secret2, "
                    f"got {','.join(secret_names)}"
                )
