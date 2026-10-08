#!/usr/bin/env bash

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Install the Playwright controller in the project's virtual environment (.venv).
# Run this script on every host.
#
# On glibc hosts it is simple: `uv sync --group browser` installs playwright.
#
# On musl hosts (e.g. Alpine Linux) this is not possible. Playwright publishes no packages
# for musl. This script works around it:
# - it installs the playwright package as if the host was a glibc host. The package itself
#   is plain Python, so it works anyway;
# - playwright also contains a helper program, the "node driver". The package ships it as a
#   glibc binary, which musl cannot run. The driver itself is plain JavaScript: the node of
#   the system runs it too. The tests point playwright to it with the environment variable
#   PLAYWRIGHT_NODEJS_PATH (see tests/integration/fixtures/playwright.py). The system node
#   must be version 20 or newer. When it is missing, the script installs the "nodejs"
#   package of the system (this needs Alpine Linux and root rights).
#
# The browser is never installed on the host. The tests use a browser that runs in a
# docker container (see tests/integration/fixtures/playwright.py).
#
# A plain `uv sync` removes playwright again. Re-run this script after it. `uv run` keeps
# playwright.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

libc_version="$(ldd --version 2>&1 | head -n1 || true)"
if [[ "$libc_version" != *musl* ]]; then
  echo "glibc detected: installing the playwright controller with 'uv sync --group browser'."
  uv sync --group browser
  echo "Playwright controller installed in .venv."
  echo "Note that a plain 'uv sync' removes it again: re-run this script afterwards."
  exit 0
fi

# Playwright publishes no musl wheels. This script installs the glibc wheels instead, so
# the platform tag must match the architecture of the host. The glibc version is left
# open: uv then picks the matching wheel, whatever manylinux version it is built for.
# uv names both supported architectures the same as uname -m does.
arch="$(uname -m)"
if [[ "$arch" != "x86_64" && "$arch" != "aarch64" ]]; then
  echo "unsupported architecture: $arch, only x86_64 and aarch64 are supported" >&2
  exit 1
fi
wheel_platform="${arch}-unknown-linux-gnu"

# The node driver needs node 20 or newer. Use the node of the system. Install the system
# package when there is none.
NODE_BIN="$(command -v node || true)"
if [ -z "$NODE_BIN" ]; then
  echo "node not found: installing the system package with 'apk add nodejs'."
  apk add --no-cache nodejs
  NODE_BIN="$(command -v node)"
fi
NODE_MAJOR="$(node --version | sed 's/^v//' | cut -d. -f1)"
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "node $NODE_MAJOR is too old: the playwright node driver needs node 20 or newer" >&2
  exit 1
fi

uv sync
PYTHON=".venv/bin/python"
PYTHON_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

# Read the pinned versions from uv.lock with `uv export`. The browser container uses the
# same playwright version.
browser_requirements="$(uv export --only-group browser --locked --no-hashes \
  --no-emit-project --format requirements-txt)"
# uv export prints one "name==version" line per package.
package_version() {
  sed -n "s/^$1==//p" <<<"$browser_requirements"
}
PLAYWRIGHT_VERSION="$(package_version playwright)"
if [ -z "$PLAYWRIGHT_VERSION" ]; then
  echo "playwright not found in uv.lock" >&2
  exit 1
fi

# Install the browser group as if the host was a glibc host, with the versions from
# uv.lock. This also installs the packages playwright needs: greenlet and pyee.
# Playwright is always installed again, even when it is already there. This restores the
# original files, in case an older version of this script replaced them.
uv pip install --python "$PYTHON" --python-platform "$wheel_platform" \
  --python-version "$PYTHON_VERSION" --reinstall-package playwright \
  -r <(printf '%s\n' "$browser_requirements")

# Run the node driver once now, with the same environment variable as the tests. If
# something is broken, this script fails here with a clear error. Otherwise the tests
# would fail later, with a hard to understand error.
PLAYWRIGHT_NODEJS_PATH="$NODE_BIN" "$PYTHON" -m playwright --version >/dev/null

echo "Playwright $PLAYWRIGHT_VERSION controller installed in .venv."
echo "Note that a plain 'uv sync' removes it again: re-run this script afterwards."
