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
# uv, to export the package's requirements from the workspace lock file below, and to
# install them
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /usr/local/bin/
# uv's cache is a BuildKit cache mount below: uv cannot hardlink across it, it must copy
ENV UV_LINK_MODE=copy
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
COPY tests/integration/fixtures/files/playwright/requirements.txt playwright-requirements.txt

# playwright is not a dependency of the test package on purpose: hosts that cannot run
# playwright (e.g. Alpine) must still be able to run the test suite. It is pinned in
# the requirements file copied above, so that renovate can bump it: docker_playwright
# hashes that file into the image tag, the image is rebuilt on a bump. uv installs the
# requirements: it is much faster than pip, and its cache can be mounted. The cache
# mounts keep the downloads out of the image layers and speed up the rebuilds on hosts
# whose BuildKit cache persists (e.g. local dev); on ephemeral CI runners it starts
# empty. The playwright browsers must NOT be installed through a cache mount: they
# live in the directory they are installed to, a cache mount would leave them out of
# the final image.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --package ess-community-integration-tests --format requirements.txt --no-hashes --no-emit-project -o requirements.txt \
    && uv pip install --system -r requirements.txt -r playwright-requirements.txt \
    && python -m playwright install --with-deps chromium

# certutil, to install the test CA in the browser's trust store. The browser then
# accepts the ingress certificates. On Linux, chromium reads the CAs it manages
# itself from the NSS database, hence libnss3-tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/*
