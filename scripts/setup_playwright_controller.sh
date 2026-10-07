#!/usr/bin/env bash

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Install the Playwright controller in the project's virtual environment (.venv), on musl
# hosts (e.g. Alpine Linux). On glibc hosts this script is not needed: `uv sync
# --group browser` installs playwright there.
#
# Playwright publishes no packages for musl. This script works around it:
# - it installs the playwright package as if the host was a glibc host. The package itself
#   is plain Python, so it works anyway;
# - playwright also contains a helper program, the "node driver". This program needs
#   glibc. The script copies the glibc files from the official Playwright docker image,
#   and uses them to start the helper program.
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
  echo "glibc detected: 'uv sync --group browser' installs the playwright controller, nothing to do."
  exit 0
fi

if [ "$(uname -m)" != "x86_64" ]; then
  echo "unsupported architecture: $(uname -m), only x86_64 is supported" >&2
  exit 1
fi

uv sync
PYTHON=".venv/bin/python"
PYTHON_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

# Read the versions from uv.lock. The browser container uses the same playwright version.
lock_version() {
  local name="name = \"$1\""
  awk -v want="$name" '$0 == want { getline; if ($1 != "version") exit 1; gsub(/"/, "", $3); print $3; exit }' uv.lock
}
PLAYWRIGHT_VERSION="$(lock_version playwright)"
GREENLET_VERSION="$(lock_version greenlet)"
PYEE_VERSION="$(lock_version pyee)"

# Install playwright as if the host was a glibc host, with the version from uv.lock.
# Playwright needs two other packages, greenlet and pyee. They are installed after this.
# Playwright is always installed again, even when it is already there. This script changes
# a file inside the package (see below). uv stores packages in a shared cache. If a
# changed package stays in the cache, uv keeps copying it back into .venv.
install_playwright() {
  uv pip install --python "$PYTHON" --python-platform x86_64-manylinux_2_40 \
    --python-version "$PYTHON_VERSION" --no-deps --reinstall-package playwright \
    "playwright==$PLAYWRIGHT_VERSION"
}
install_playwright
uv pip install --python "$PYTHON" "greenlet==$GREENLET_VERSION" "pyee==$PYEE_VERSION"

DRIVER_DIR="$("$PYTHON" -c 'import playwright, pathlib; print(pathlib.Path(playwright.__file__).parent / "driver")')"
if [ "$(head -c 4 "$DRIVER_DIR/node" 2>/dev/null || true)" != $'\x7fELF' ]; then
  # A changed file ended up in uv's cache. Empty the cache and install again.
  uv cache clean playwright
  install_playwright
  DRIVER_DIR="$("$PYTHON" -c 'import playwright, pathlib; print(pathlib.Path(playwright.__file__).parent / "driver")')"
fi

# Copy the glibc files from the official Playwright docker image, of the same playwright
# version. The helper program needs them to run.
GLIBC_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ess-helm/playwright-driver-glibc/$PLAYWRIGHT_VERSION"
if [ ! -f "$GLIBC_DIR/ld-linux-x86-64.so.2" ]; then
  rm -rf "$GLIBC_DIR"
  mkdir -p "$GLIBC_DIR"
  docker run --rm --user "$(id -u):$(id -g)" -v "$GLIBC_DIR:/out" \
    --entrypoint /bin/bash "mcr.microsoft.com/playwright:v$PLAYWRIGHT_VERSION" \
    -c 'cp -L /usr/lib/x86_64-linux-gnu/{ld-linux-x86-64.so.2,libc.so.6,libm.so.6,libdl.so.2,libpthread.so.0,librt.so.1,libstdc++.so.6,libgcc_s.so.1,libresolv.so.2,libutil.so.1} /out/'
fi

# Replace the helper program with a small script. The script starts the real program
# through the glibc files copied above. Installing playwright again restores the original
# program. Then this script must wrap it again.
# The new script is first written to a temporary file, then moved into place. This way the
# file in uv's cache is never changed.
if [ "$(head -c 4 "$DRIVER_DIR/node" 2>/dev/null || true)" = $'\x7fELF' ]; then
  mv "$DRIVER_DIR/node" "$DRIVER_DIR/node.bin"
fi
printf '#!/bin/sh\nexec "%s/ld-linux-x86-64.so.2" --library-path "%s" "%s/node.bin" "$@"\n' \
  "$GLIBC_DIR" "$GLIBC_DIR" "$DRIVER_DIR" >"$DRIVER_DIR/node.wrapper"
mv "$DRIVER_DIR/node.wrapper" "$DRIVER_DIR/node"
chmod +x "$DRIVER_DIR/node"

# Run the helper program once now. If something is broken, this script fails here with a
# clear error. Otherwise the tests would fail later, with a hard to understand error.
"$DRIVER_DIR/node" --version >/dev/null

echo "Playwright $PLAYWRIGHT_VERSION controller installed in .venv."
echo "Note that a plain 'uv sync' removes it again: re-run this script afterwards."
