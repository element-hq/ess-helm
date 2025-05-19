# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import pytest

from . import all_components_details, secret_values_files_to_test, values_files_to_test


def test_all_components_covered():
    expected_folders = [details.value_file_prefix for details in all_components_details]

    templates_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/templates")
    for contents in templates_folder.iterdir():
        if not contents.is_dir():
            continue
        if contents.name in ("ess-library",):
            continue

        assert contents.name in expected_folders


@pytest.mark.parametrize("values_file", values_files_to_test | secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
def test_component_has_values_file(values_file):
    ci_folder = Path(__file__).parent.parent.parent / Path("charts/matrix-stack/ci")
    values_file = ci_folder / values_file
    assert values_file.exists()
