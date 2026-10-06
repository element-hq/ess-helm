# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import re
import time
from collections.abc import AsyncIterator
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, cast

import pytest
from python_on_whales import Container, docker

try:
    from playwright.async_api import Browser, async_playwright
except ImportError:
    # Playwright is only installed in the development environment. `uv sync
    # --group browser` installs it on glibc hosts, scripts/setup_playwright_controller.sh
    # on musl ones. When it is missing, the browser tests are skipped instead of failing
    # with an error.
    Browser = None  # type: ignore[assignment, misc]
    async_playwright = None  # type: ignore[assignment, misc]

TESTS_DIR = Path(__file__).parent.parent.parent
DOCKERFILE = TESTS_DIR / "integration" / "docker" / "Dockerfile"

# The browser server prints the websocket address it listens on, e.g. ws://127.0.0.1:xxxx/
_WS_ENDPOINT_PATTERN = re.compile(r"ws://\S+")
_BROWSER_SERVER_STARTUP_TIMEOUT = 60


def _require_controller() -> Any:
    if async_playwright is None:
        pytest.skip("playwright is not installed: see scripts/setup_playwright_controller.sh")
    return async_playwright


@pytest.fixture(scope="session")
async def browser() -> AsyncIterator[Browser]:
    """A Chromium running in a docker container. The tests talk to it over a websocket.

    The browser runs in a docker container, so nothing has to be installed on the host.
    The tests also work on hosts where Playwright cannot install or run a browser locally
    (e.g. Alpine Linux). The container uses the network of the host. So the browser can
    reach the ingress on the loopback interface. And the tests can reach the browser
    server's websocket address.
    """
    controller = _require_controller()
    playwright_version = package_version("playwright")
    # The browser container must use the same playwright version as the controller.
    # Otherwise they cannot talk to each other.
    image_tag = f"ess-helm-playwright-browser:v{playwright_version}"
    if not docker.image.exists(image_tag):
        docker.build(
            context_path=DOCKERFILE.parent,
            file=DOCKERFILE,
            tags=[image_tag],
            build_args={"PLAYWRIGHT_VERSION": playwright_version},
        )
    container = docker.run(
        image_tag,
        detach=True,
        init=True,
        remove=True,
        networks=["host"],
        shm_size="1g",
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
        if match := _WS_ENDPOINT_PATTERN.search(_container_logs(container)):
            return match.group(0)
        if not docker.container.inspect(container).state.running:
            raise RuntimeError(f"browser server container exited:\n{_container_logs(container)}")
        await asyncio.sleep(0.5)
    raise TimeoutError(f"browser server did not print its websocket endpoint within {_BROWSER_SERVER_STARTUP_TIMEOUT}s")


def _container_logs(container: Container) -> str:
    # python_on_whales says this function can also return another type. Here it always
    # returns a string.
    return cast("str", docker.container.logs(container))


@pytest.fixture
async def browser_page(browser: Browser):
    # The browser does not know the test CA. So it does not check the certificates.
    # Chromium sends *.localhost names to the loopback address. The ingress listens there.
    context = await browser.new_context(ignore_https_errors=True)
    page = await context.new_page()
    yield page
    await context.close()
