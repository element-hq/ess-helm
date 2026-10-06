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
# uv, to export the package's requirements from the workspace lock file below
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /usr/local/bin/
# Only the files needed to export the test package's requirements are copied, never
# the package code itself: the container never runs the code baked into the image.
# At runtime, the host's tests directory is mounted over /ess-helm/tests, and
# PYTHONPATH points to it. cloudpickle only pickles the code of the test bodies by
# value: the rpyc server, the test package and everything the test bodies import by
# name come from that mount. Code changes therefore do not need a rebuild of the
# image: copying the real tests directory here would invalidate the cache of the
# expensive layers below on every code change. The lock file pins the exact versions
# installed in the image; it must be regenerated when the requirements change.
COPY pyproject.toml uv.lock ./
COPY tests/pyproject.toml tests/

# playwright is not a dependency of the test package on purpose: hosts that cannot run
# playwright (e.g. Alpine) must still be able to run the test suite.
RUN uv export --frozen --package ess-community-integration-tests --format requirements.txt --no-hashes --no-emit-project -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt "playwright>=1.62.0" \
    && python -m playwright install --with-deps chromium

# certutil, to install the test CA in the browser's trust store. The browser then
# accepts the ingress certificates. On Linux, chromium reads the CAs it manages
# itself from the NSS database, hence libnss3-tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/*
