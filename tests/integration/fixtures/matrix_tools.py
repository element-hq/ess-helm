# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
from pathlib import Path

import pytest
from python_on_whales import Image, docker


@pytest.fixture(scope="session")
def build_matrix_tools():
    # Until the image is made publicly available
    # In local runs we always have to build it
    if os.environ.get("BUILD_MATRIX_TOOLS"):
        project_folder = Path(__file__).parent.parent.parent.parent.resolve()
        docker.buildx.bake(
            files=str(project_folder / "docker-bake.hcl"),
            targets="matrix-tools",
            set={"*.tags": "localhost:5000/matrix-tools:pytest"},
            load=True,
        )


@pytest.fixture(scope="session")
def loaded_matrix_tools(cluster, build_matrix_tools: Image):
    # Until the image is made publicly available
    # In local runs we always have to build it
    if os.environ.get("BUILD_MATRIX_TOOLS"):
        docker.push("localhost:5000/matrix-tools:pytest")
        matrix_tools = docker.image.inspect("localhost:5000/matrix-tools:pytest")
        return {
            "repository": "matrix-tools",
            "registry": "localhost:5000",
            "digest": matrix_tools.repo_digests[0].split("@")[-1],
            "tag": "pytest",
        }
    # CI builds the image in a dedicated job and passes its reference:
    # ghcr.io/element-hq/ess-helm/matrix-tools:sha-0123abcd. The registry and the repository
    # match the chart defaults, only the tag differs.
    elif matrix_tools_image := os.environ.get("MATRIX_TOOLS_IMAGE"):
        return {"tag": matrix_tools_image.rpartition(":")[2]}
    else:
        return {}
