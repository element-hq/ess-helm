# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Image for the integration tests run by the docker_playwright decorator, e.g. the
# playwright browser tests (playwright cannot run on every host, e.g. Alpine).
#
# The Python version matches the host running pytest. At runtime, the host's tests
# directory is mounted over the image's one. Code changes therefore do not need a
# rebuild of the image.
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

WORKDIR /build
# The package is copied so that the `pip install .` below can build it and install all
# of its dependencies into the image. That is the only reason for this copy. At
# runtime, the host's tests directory is mounted over /ess-helm/tests, and PYTHONPATH
# points to it. The container always runs the host's code. Code changes do not need a
# rebuild of the image.
COPY pyproject.toml README.md ./
COPY integration ./integration

# playwright is not a dependency of the test package on purpose: hosts that cannot run
# playwright (e.g. Alpine) must still be able to run the test suite.
RUN pip install --no-cache-dir . "playwright>=1.62.0" \
    && python -m playwright install --with-deps chromium

# certutil, to install the test CA in the browser's trust store. The browser then
# accepts the ingress certificates. On Linux, chromium reads the CAs it manages
# itself from the NSS database, hence libnss3-tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/*
