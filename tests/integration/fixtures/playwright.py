# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import hashlib
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import pytest
from python_on_whales import Container, docker

from ..artifacts import CertKey

try:
    from playwright.async_api import Browser, async_playwright
except ImportError:
    # Playwright is only installed in the development environment, by
    # scripts/setup_playwright_controller.sh. When it is missing, the browser tests are
    # skipped instead of failing with an error.
    Browser = None  # type: ignore[assignment, misc]
    async_playwright = None  # type: ignore[assignment, misc]

# The docker image the browser runs in. CI builds it and puts it in the registry under this
# name. The tag is computed by image_reference(). This way the tests can download the image
# instead of building it on every CI run. Hosts that cannot reach the registry build it
# locally, with the same name and tag.
IMAGE_NAME = "ghcr.io/element-hq/ess-helm/playwright-browser"
DOCKERFILE = Path(__file__).parent / "files" / "playwright" / "Dockerfile"
REPO_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

# The path where the test CA certificate is mounted in the container. The start script of
# the image installs it in the browser before the browser server starts (see the Dockerfile).
CA_MOUNT_PATH = "/ess-helm-test-ca.pem"

# The browser server prints the websocket address it listens on, e.g. ws://127.0.0.1:xxxx/
_WS_ENDPOINT_PATTERN = re.compile(r"ws://\S+")
_BROWSER_SERVER_STARTUP_TIMEOUT = 60


def image_reference() -> str:
    """The name and tag of the docker image the browser runs in.

    The tag says exactly what the image is built from:
    - the playwright version. It sets the base image and the npm package the Dockerfile
      installs on top of it;
    - a hash of the Dockerfile directory (the Dockerfile and the start script it copies).
    So any change gives a new tag, and so a new image.
    CI uses this same function to name the image it publishes.
    """
    playwright_version = package_version("playwright")
    context_hash = hashlib.sha256(
        b"".join(file.read_bytes() for file in sorted(DOCKERFILE.parent.iterdir()) if file.is_file())
    ).hexdigest()[:12]
    return f"{IMAGE_NAME}:v{playwright_version}-{context_hash}"


def _ensure_image() -> str:
    """Make sure the browser image is on this machine: download it from the registry, or
    build it when the download fails. That can happen when CI has not published the image
    yet, or when this machine cannot log in to the registry (e.g. a CI run of a fork)."""
    reference = image_reference()
    if docker.image.exists(reference):
        return reference
    try:
        docker.pull(reference)
    except Exception:
        docker.buildx.bake(
            files=REPO_ROOT / "docker-bake.hcl",
            targets="playwright-browser",
            set={
                "*.tags": reference,
                "*.args.PLAYWRIGHT_VERSION": package_version("playwright"),
            },
            load=True,
        )
    return reference


def _set_playwright_node() -> None:
    """Configure which node version to use on the controller.

    Playwright ships its node driver as a glibc binary. On musl hosts (e.g. Alpine Linux)
    that binary cannot run. The driver itself is plain JavaScript: a node of the system
    runs it too. Playwright reads the node path from the PLAYWRIGHT_NODEJS_PATH
    environment variable. The setup script checks that the node is new enough.
    """
    if sys.platform != "linux" or "PLAYWRIGHT_NODEJS_PATH" in os.environ:
        return
    try:
        os.confstr("CS_GNU_LIBC_VERSION")  # works only on a glibc host
    except OSError:
        pass  # musl host: the bundled node cannot run
    else:
        return  # glibc host: the bundled node runs
    node = shutil.which("node")
    if node is not None:
        os.environ["PLAYWRIGHT_NODEJS_PATH"] = node


def _require_controller() -> Any:
    if async_playwright is None:
        pytest.skip("playwright is not installed: run scripts/setup_playwright_controller.sh")
    _set_playwright_node()
    return async_playwright


@pytest.fixture(scope="session")
async def browser(root_ca: CertKey) -> AsyncIterator[Browser]:
    """A Chromium running in a docker container. The tests talk to it over a websocket.

    The browser runs in a docker container, so nothing has to be installed on the host.
    The tests also work on hosts where Playwright cannot install or run a browser locally
    (e.g. Alpine Linux). The container uses the network of the host. So the browser can
    reach the ingress on the loopback interface. And the tests can reach the browser
    server's websocket address.

    The test CA signs the certificates of the ingress. It is mounted into the container.
    The image installs it in the browser before the browser server starts. So the browser
    accepts the certificates of the ingress.
    """
    controller = _require_controller()
    with tempfile.TemporaryDirectory() as ca_dir:
        ca_file = Path(ca_dir) / "ess-helm-test-ca.pem"
        ca_file.write_text(root_ca.cert_as_pem())
        container = docker.run(
            _ensure_image(),
            # The start script of the image installs the mounted CA certificate in the
            # browser. Then it starts the browser server. The server prints its websocket
            # address. It listens on a random port of the loopback interface.
            detach=True,
            init=True,
            remove=True,
            networks=["host"],
            shm_size="1g",
            volumes=[(ca_file, CA_MOUNT_PATH, "ro")],
        )
        try:
            ws_endpoint = await _wait_for_ws_endpoint(container)
            async with controller() as playwright:
                browser = await playwright.chromium.connect(ws_endpoint)
                yield browser
                await browser.close()
        finally:
            docker.container.remove(container, force=True)


async def _wait_for_ws_endpoint(container: Container) -> str:
    deadline = time.monotonic() + _BROWSER_SERVER_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if match := _WS_ENDPOINT_PATTERN.search(container.logs()):
            return match.group(0)
        if not docker.container.inspect(container).state.running:
            raise RuntimeError(f"browser server container exited:\n{container.logs()}")
        await asyncio.sleep(0.5)
    raise TimeoutError(f"browser server did not print its websocket endpoint within {_BROWSER_SERVER_STARTUP_TIMEOUT}s")


@pytest.fixture
async def browser_page(browser: Browser):
    # The browser knows the test CA (see the browser fixture). So it accepts the
    # certificates of the ingress. Chromium sends *.localhost names to the loopback
    # address. The ingress listens there.
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()
