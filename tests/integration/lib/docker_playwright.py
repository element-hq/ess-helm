# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Run async test bodies in a container with playwright ready, from a host that may not be
able to run them (e.g. Alpine).

A test marked `@pytest.mark.asyncio_cooperative` and `@pytest.mark.docker_playwright`
(`install()` teaches pytest-asyncio-cooperative about the marker) has its fixtures
resolved on the host as for any other cooperative test, and its body runs inside the
container: the test function and the fixture values are sent there with cloudpickle, which
serializes the function by value, so the exact code that was collected runs remotely,
without the container importing (or collecting) the test modules. The container runs an
rpyc server (see integration/docker/rpyc_server.py) which the host opens a connection to
for each test, and it shares the host network so that the browser can reach the k3d
ingress proxy on the loopback interface.
"""

import asyncio
import collections.abc
import contextlib
import inspect
import sys
import threading
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import cloudpickle
import pytest
import rpyc
from pytest_asyncio_cooperative.fixtures import fill_fixtures
from python_on_whales import docker

TESTS_DIR = Path(__file__).parent.parent.parent
IMAGE_NAME = "ess-helm-integration-tests"
CONTAINER_TESTS_DIR = "/ess-helm/tests"
SERVER_PATH = f"{CONTAINER_TESTS_DIR}/integration/docker/rpyc_server.py"
SERVER_PORT = 47474
DEFAULT_TIMEOUT = 600

_container_id: str | None = None
# Reentrant: _connect_run holds it while calling _start_container, which takes it too
_container_lock = threading.RLock()

TestFunction = Callable[..., Coroutine[Any, Any, None]]


class DockerPlaywrightTestFailure(Exception):
    pass


def _dumps_payload(function: TestFunction, kwargs: dict[str, Any], timeout: float) -> bytes:
    module = sys.modules[function.__module__]
    # Pickle the test body by value, so that the container runs the exact code that was
    # collected on the host. Everything else goes by reference: the test package is
    # mounted in the container and its dependencies are installed in the image.
    cloudpickle.register_pickle_by_value(module)
    try:
        return cloudpickle.dumps({"func": function, "kwargs": kwargs, "timeout": timeout})
    finally:
        cloudpickle.unregister_pickle_by_value(module)


def _image_tag() -> str:
    # cloudpickle payloads are only readable by the same cloudpickle version, the code
    # objects they embed only run on the same Python minor version, and the rpyc wire
    # protocol is only guaranteed within a major version: rebuild the image when any
    # of them changes
    python = f"py{sys.version_info.major}.{sys.version_info.minor}"
    return f"{IMAGE_NAME}:{python}-cp{cloudpickle.__version__}-r{rpyc.__version__}"


def _container_alive() -> bool:
    if _container_id is None:
        return False
    try:
        return bool(docker.container.inspect(_container_id).state.running)
    except Exception:
        return False


def _start_container() -> str:
    """Start the container the decorated tests run in, if not started yet.

    It lives for the whole pytest session: browser tests typically run in the same session
    as the async tests that deploy the stack, and starting the container is not free. Its
    main process is the rpyc server the host connects to.
    """
    global _container_id
    with _container_lock:
        if _container_id is not None:
            return _container_id

        tag = _image_tag()
        if not docker.image.exists(tag):
            docker.build(
                context_path=TESTS_DIR,
                file=TESTS_DIR / "integration" / "fixtures" / "files" / "playwright" / "Dockerfile",
                tags=[tag],
                build_args={"PYTHON_VERSION": f"{sys.version_info.major}.{sys.version_info.minor}"},
            )

        container = docker.run(
            tag,
            command=["python", SERVER_PATH, str(SERVER_PORT)],
            detach=True,
            init=True,
            networks=["host"],
            remove=True,
            shm_size="1g",
            envs={"PYTHONPATH": CONTAINER_TESTS_DIR},
            volumes=[(TESTS_DIR, CONTAINER_TESTS_DIR, "ro")],
        )
        _container_id = container.id
        return _container_id


def _connect_run() -> rpyc.Connection:
    """Open a connection to the container's rpyc server for one test run.

    The server runs each connection's requests in their own thread, so test bodies sent on
    separate connections run in parallel inside the container. The container is restarted
    if it died, e.g. after the machine ran out of memory.
    """
    global _container_id
    with _container_lock:
        if not _container_alive():
            _container_id = None
        _start_container()

        deadline = time.monotonic() + 60
        while True:
            try:
                return rpyc.connect("127.0.0.1", SERVER_PORT, config={"sync_request_timeout": None})
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)


def stop_container() -> None:
    """Stop the test container, if one was started. Called when the pytest session ends."""
    global _container_id
    with _container_lock:
        if _container_id is not None:
            docker.remove(_container_id, force=True)
            _container_id = None


def _run_in_container(function: TestFunction, kwargs: dict[str, Any], timeout: float) -> None:
    payload = _dumps_payload(function, kwargs, timeout)
    connection = _connect_run()
    try:
        async_result = rpyc.async_(connection.root.run)(payload)
        # The container enforces the timeout on the test itself; the extra minute is a
        # backstop for the case where it cannot, e.g. because the machine is overloaded
        async_result.set_expiry(timeout + 60)
        try:
            output = async_result.value
        except rpyc.AsyncResultTimeout:
            raise DockerPlaywrightTestFailure(f"The test did not report back within {timeout + 60} seconds") from None
        except Exception as error:
            raise DockerPlaywrightTestFailure(f"The test failed inside the playwright container:\n{error}") from None
    finally:
        connection.close()
    if output:
        print(output, end="")


async def _run_item(item: pytest.Function) -> None:
    """Run a docker_playwright-marked test in the container, in the cooperative loop.

    Mirrors the plugin's own test wrapper: the fixtures are filled on the host as for any
    other cooperative test, but instead of awaiting the test body it is sent with its
    fixture values to the container, and awaited from a thread so that the other
    cooperative tests keep running. The item attributes and the teardowns are what the
    plugin uses for its durations and reporting.
    """
    marker = item.get_closest_marker("docker_playwright")
    timeout = (marker.kwargs.get("timeout") if marker else None) or DEFAULT_TIMEOUT
    function = item.function
    fixture_names = list(inspect.signature(function).parameters)

    # The cooperative plugin reads these attributes on the item for its durations and
    # reporting, in the same way as in its own test wrapper, which this mirrors
    report_item: Any = item
    report_item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    report_item.stop_setup = time.time()

    # A misalignment between the fixture names and values would mean the remote body is
    # called with the wrong arguments, so fail loudly instead of truncating
    kwargs = dict(zip(fixture_names, fixture_values, strict=True))

    async def do_teardowns():
        report_item.start_teardown = time.time()
        for teardown in teardowns:
            if isinstance(teardown, collections.abc.Iterator):
                with contextlib.suppress(StopIteration):
                    teardown.__next__()
            else:
                with contextlib.suppress(StopAsyncIteration):
                    await teardown.__anext__()
        report_item.stop_teardown = time.time()

    report_item.start = time.time()
    try:
        await asyncio.to_thread(_run_in_container, function, kwargs, timeout)
    except BaseException:
        # Do the teardowns, otherwise we might leave fixtures with locks acquired
        report_item.stop = time.time()
        await do_teardowns()
        raise
    report_item.stop = time.time()
    await do_teardowns()


def install() -> None:
    """Teach pytest-asyncio-cooperative to run docker_playwright-marked tests remotely.

    It plugs into the same dispatch the plugin uses for its hypothesis support, so that
    marked tests are collected, timed, torn down and reported like any other test. Called
    from the conftest at configure time.
    """
    from pytest_asyncio_cooperative import plugin as cooperative

    original_item_to_task = cooperative.item_to_task

    def item_to_task(item: pytest.Function):
        if "docker_playwright" in item.keywords:
            return _run_item(item)
        return original_item_to_task(item)

    cooperative.item_to_task = item_to_task
