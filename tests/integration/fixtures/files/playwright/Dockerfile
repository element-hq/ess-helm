# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# This image runs a Playwright browser server. The integration tests (fixtures/playwright.py)
# drive the Chromium inside it over a websocket. No browser has to be installed on the
# machine that runs the tests.

ARG PLAYWRIGHT_VERSION
FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}

# The base image already contains the browser files of its own Playwright version. But it
# does not contain the playwright npm package. Install it, so that `run-server` serves
# exactly those browser files. And nothing is downloaded through npx each time a container
# starts.
# The version must be written again here: an ARG before FROM is only visible to FROM.
ARG PLAYWRIGHT_VERSION
RUN npm install --global playwright@${PLAYWRIGHT_VERSION}

# certutil. The start script below uses it to install the test CA certificate in the browser.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/*

COPY --chmod=755 start-browser-server.sh /usr/local/bin/start-browser-server

CMD ["start-browser-server"]
