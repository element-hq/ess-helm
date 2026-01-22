# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import pathlib
from pathlib import Path

import pytest

from . import all_components_details, secret_values_files_to_test, values_files_to_test


def test_all_components_covered():
    expected_folders = [details.value_file_prefix for details in all_components_details]

    templates_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/templates")
    for contents in templates_folder.iterdir():
        if not contents.is_dir():
            continue
        if contents.name in (
            "ess-library",
            "z_validation",
        ):
            continue

        assert contents.name in expected_folders


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
def test_component_has_values_file(values_file):
    ci_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/ci")
    extra_ci_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/ci_extra")
    ci_values_file = ci_folder / values_file
    extra_values_file = extra_ci_folder / values_file
    assert ci_values_file.exists() or extra_values_file.exists()


@pytest.mark.asyncio_cooperative
def test_validation_messages_will_be_first_processed_template():
    templates_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/templates")
    paths = []
    for path, _, files in os.walk(templates_folder):
        for name in files:
            paths.append(pathlib.PurePath(path, name).relative_to(templates_folder))

    # https://github.com/helm/helm/blob/v3.18.0/pkg/engine/engine.go#L347-L356
    # https://github.com/helm/helm/blob/v3.18.0/pkg/engine/engine_test.go#L37-L69
    # We don't need to worry about sub-charts, so we just need to sort the paths by how nested they are
    # then alphabetically for identically nested paths and finally reverse it to get what Helm would load first
    # This is important as templates that call `tpl` seem to evaluate that call eagerly and fail in an ugly way
    # and so we want our validation template to have run first
    paths.sort(key=lambda path: (len(path.parents), path), reverse=True)
    assert paths[0] == (Path("z_validation") / "validation.txt")
