# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# This image runs a Playwright browser server. The integration tests (fixtures/playwright.py)
# drive the Chromium inside it over a websocket. No browser has to be installed on the
# machine that runs the tests.

ARG PLAYWRIGHT_VERSION
FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}

# The base image already contains the browser files of its own Playwright version. But it
# does not contain the playwright npm package. Install it, so that `launch-server` serves
# exactly those browser files.
# The version must be written again here: an ARG before FROM is only visible to FROM.
ARG PLAYWRIGHT_VERSION
RUN npm install --global playwright@${PLAYWRIGHT_VERSION}

# The browser server prints its websocket address on stdout, e.g.
# ws://127.0.0.1:xxxx/<token>
CMD ["playwright", "launch-server", "--browser", "chromium"]
