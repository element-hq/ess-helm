# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Image for the integration tests run by the docker_playwright decorator, e.g. the
# playwright browser tests (playwright cannot run on every host, e.g. Alpine).
#
# The Python major.minor version matches the host running pytest, and the tests
# directory is mounted over the one baked in at runtime, so that code changes do
# not require a rebuild.
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

WORKDIR /build
COPY pyproject.toml README.md ./
COPY integration ./integration

# playwright is not a dependency of the test package on purpose: hosts that cannot run
# playwright (e.g. Alpine) must still be able to run the test suite.
RUN pip install --no-cache-dir . "playwright>=1.62.0" \
    && python -m playwright install --with-deps chromium
