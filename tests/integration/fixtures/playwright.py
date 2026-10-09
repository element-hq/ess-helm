# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import time
from collections.abc import AsyncIterator
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import pytest
from python_on_whales import Container, docker

from ..artifacts import CertKey
from .cluster import PotentiallyExistingK3dCluster

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

# The environment variables the tests pass to the browser container. The start script of
# the image reads them, writes the files it needs, and installs the CA certificate in the
# browser before the browser server starts (see the Dockerfile). The CA is a PEM string,
# base64 encoded so that it survives as a single value.
CA_ENV_VAR = "ESS_HELM_BROWSER_CA_PEM"
LAUNCH_CONFIG_ENV_VAR = "ESS_HELM_BROWSER_LAUNCH_CONFIG"

# The browser server prints the websocket address it listens on, e.g. ws://0.0.0.0:xxxx/<random path>.
# The host of the printed address is only meaningful inside the container. The tests connect
# to the IP of the container instead, so the host part is replaced (see _wait_for_browser).
_WS_ENDPOINT_PATTERN = re.compile(r"ws://\S+:(?P<port>\d+)(?P<path>/\S*)")
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


def _container_ip(container: Container, network: str) -> str:
    """The IP of a container on a docker network."""
    networks = docker.container.inspect(container).network_settings.networks
    assert networks, f"the container is not attached to the network {network}"
    ip = networks[network].ip_address
    assert ip, f"the container has no IP on the network {network}"
    return ip


def _traefik_ingress_ip(cluster: PotentiallyExistingK3dCluster, network: str) -> str:
    """The IP of the Traefik ingress controller on the docker network of the cluster.

    The load balancer container of k3d listens on the ports 80 and 443 of the docker
    network, and forwards them to Traefik. So this IP is how the ingress is reached from
    the containers on that network, e.g. the browser container.
    """
    load_balancer = docker.container.inspect(f"k3d-{cluster.cluster_name}-serverlb")
    return _container_ip(load_balancer, network)


def _launch_config(ingress_ip: str) -> dict[str, Any]:
    """The launch config of the browser server, as playwright expects it.

    The server listens on all interfaces, so the tests can reach its websocket through the
    docker network of the cluster.

    The browser resolves the *.localhost names of the tests to the IP of the ingress.
    Chromium has that built in: it sends them to the loopback address. That is why the
    mapping cannot go into /etc/hosts: Chromium never looks there for these names, and
    /etc/hosts has no wildcards anyway. The host resolver rules of Chromium override its
    built-in loopback mapping.
    """
    return {
        "host": "0.0.0.0",
        "args": [f"--host-resolver-rules=MAP *.localhost {ingress_ip}"],
    }


@pytest.fixture(scope="session")
async def browser(cluster: PotentiallyExistingK3dCluster, root_ca: CertKey) -> AsyncIterator[Browser]:
    """A Chromium running in a docker container. The tests talk to it over a websocket.

    The browser runs in a docker container, so nothing has to be installed on the host.
    The tests also work on hosts where Playwright cannot install or run a browser locally
    (e.g. Alpine Linux).

    The container is attached to the docker network of the k3d cluster, not to the network
    of the host. So the tests do not rely on host networking, and they also work when they
    run inside a container themselves: the websocket address of the browser server is the
    IP of the browser container on that network.

    On that network, the ingress is reached at the IP of the k3d load balancer that fronts
    Traefik. The browser resolves the *.localhost names of the tests to that IP (see
    _launch_config).

    The test CA signs the certificates of the ingress. It is passed to the container in
    an environment variable (see CA_ENV_VAR). The image installs it in the browser before
    the browser server starts. So the browser accepts the certificates of the ingress.
    """
    controller = _require_controller()
    network = f"k3d-{cluster.cluster_name}"
    container = docker.run(
        _ensure_image(),
        # The start script of the image writes the CA certificate of the environment
        # variable into a file and installs it in the browser. Then it starts the browser
        # server with the launch config of the other environment variable. The server
        # prints its websocket address. It listens on a random port of all interfaces.
        detach=True,
        init=True,
        remove=True,
        networks=[network],
        shm_size="1g",
        envs={
            CA_ENV_VAR: base64.b64encode(root_ca.cert_as_pem().encode()).decode(),
            LAUNCH_CONFIG_ENV_VAR: base64.b64encode(
                json.dumps(_launch_config(_traefik_ingress_ip(cluster, network))).encode()
            ).decode(),
        },
    )
    container_ip = _container_ip(container, network)
    try:
        async with controller() as playwright:
            browser = await _wait_for_browser(playwright, container, container_ip)
            yield browser
            await browser.close()
    finally:
        docker.container.remove(container, force=True)


async def _wait_for_browser(playwright: Any, container: Container, container_ip: str) -> Browser:
    """A connection to the browser server in the container.

    The websocket address is read from the container logs. The server prints it, and its
    random path is not known otherwise. The printed host is replaced with the IP of the
    container on the network of the cluster: the printed one is only reachable inside the
    container. The printed line alone does not prove that the server accepts connections.
    So the connection is the real test: it is retried until the server accepts it, and the
    last error is reported when it never does.
    """
    deadline = time.monotonic() + _BROWSER_SERVER_STARTUP_TIMEOUT
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if match := _WS_ENDPOINT_PATTERN.search(container.logs()):
            endpoint = f"ws://{container_ip}:{match['port']}{match['path']}"
            try:
                return await playwright.chromium.connect(endpoint, timeout=2000)
            except Exception as error:
                # The server printed its address but refused the connection. It may
                # not be ready yet. Try again until the deadline.
                last_error = error
        if not docker.container.inspect(container).state.running:
            raise RuntimeError(f"browser server container exited:\n{container.logs()}")
        await asyncio.sleep(0.5)
    raise TimeoutError(
        f"could not connect to the browser server within {_BROWSER_SERVER_STARTUP_TIMEOUT}s: {last_error}"
    )


@pytest.fixture
async def browser_page(browser: Browser):
    # The browser knows the test CA (see the browser fixture). So it accepts the
    # certificates of the ingress. The browser resolves the *.localhost names of the tests
    # to the IP of the ingress (see the browser fixture).
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()
