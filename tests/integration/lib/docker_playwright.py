# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Run async test bodies in a container with playwright ready, from a host that may not be
able to run them (e.g. Alpine).

A test marked `@pytest.mark.asyncio_cooperative` and `@pytest.mark.docker_playwright`
(`install()` registers the marker with pytest-asyncio-cooperative) has its fixtures set
up on the host, like for any other cooperative test. Its body runs inside the container.
The test function and the fixture values are sent there with cloudpickle, which
serializes the code of the function itself. The exact code that was collected runs
remotely. The container does not import (or collect) the test modules. It runs an rpyc
server (see integration/docker/rpyc_server.py). The host opens one connection to it per
test. The container shares the network of the host, so the browser can reach the k3d
ingress proxy on localhost. When a test fails, the traces of its browser contexts come
back on the same connection. They are saved to playwright-traces/ (the only mount of
the container is read-only), to be opened in the playwright trace viewer.
"""

import asyncio
import collections.abc
import contextlib
import inspect
import re
import sys
import threading
import time
from collections.abc import Callable, Coroutine, Sequence
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
# Where the failure traces sent back by the container are saved. It is next to the
# ess-helm-logs directory written by collect-ess-logs, which the CI job uploads
# together with the traces
TRACES_DIR = Path("playwright-traces")

_container_id: str | None = None
# The same thread can take this lock more than once (it is an RLock): _connect_run
# holds it while calling _start_container, which takes it too
_container_lock = threading.RLock()

TestFunction = Callable[..., Coroutine[Any, Any, None]]


class DockerPlaywrightTestFailure(Exception):
    pass


def _dumps_payload(function: TestFunction, kwargs: dict[str, Any], timeout: float) -> bytes:
    module = sys.modules[function.__module__]
    # Pickle the code of the test body itself. The container then runs the exact code
    # that was collected on the host. Everything else is pickled by name: the test
    # package is mounted in the container, and its dependencies are in the image
    cloudpickle.register_pickle_by_value(module)
    try:
        return cloudpickle.dumps({"func": function, "kwargs": kwargs, "timeout": timeout})
    finally:
        cloudpickle.unregister_pickle_by_value(module)


def _image_tag() -> str:
    # A cloudpickle payload can only be read by the same cloudpickle version. The code
    # it contains only runs on the same Python minor version. The rpyc protocol is
    # only guaranteed within the same major version. The image must be rebuilt when
    # any of them changes
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
    """Start the container the decorated tests run in, if it is not started yet.

    It lives for the whole pytest session. Browser tests usually run in the same session
    as the async tests that deploy the stack, and starting the container takes time.
    Its main process is the rpyc server the host connects to.
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

    The server runs each connection in its own thread. Test bodies sent on separate
    connections therefore run at the same time inside the container. The container is
    started again if it stopped, e.g. because the machine ran out of memory.
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


def _write_failure_traces(test_name: str, traces: Sequence[bytes]) -> list[Path]:
    """Write the traces the container recorded for the failing test. Returns their paths.

    The container cannot save them itself. Its only mount is read-only, so they come
    back with the failure, over the same rpyc connection.
    """
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w.-]", "_", test_name)
    paths = [TRACES_DIR / f"{name}-{index}.zip" for index in range(len(traces))]
    for path, trace in zip(paths, traces, strict=True):
        path.write_bytes(trace)
    return paths


def _run_in_container(function: TestFunction, test_name: str, kwargs: dict[str, Any], timeout: float) -> None:
    payload = _dumps_payload(function, kwargs, timeout)
    connection = _connect_run()
    try:
        async_result = rpyc.async_(connection.root.run)(payload)
        # The container applies the timeout to the test itself. The extra minute is a
        # safety margin, in case the container cannot apply it (e.g. the machine is
        # overloaded)
        async_result.set_expiry(timeout + 60)
        try:
            output, error, traces = async_result.value
        except rpyc.AsyncResultTimeout:
            raise DockerPlaywrightTestFailure(f"The test did not report back within {timeout + 60} seconds") from None
        except Exception as failure:
            raise DockerPlaywrightTestFailure(f"The test failed inside the playwright container:\n{failure}") from None
    finally:
        connection.close()

    if error:
        # The container sends the traces of the failing test's browser contexts back
        # with the failure. Its only mount is read-only, so it cannot save them itself
        paths = _write_failure_traces(test_name, traces)
        message = f"The test failed inside the playwright container:\n{error}"
        for path in paths:
            message += f"\nFailure trace saved to {path}, open it with: npx playwright show-trace {path}"
        raise DockerPlaywrightTestFailure(message)
    if output:
        print(output, end="")


async def _run_item(item: pytest.Function) -> None:
    """Run a docker_playwright-marked test in the container, inside the cooperative loop.

    This works like the plugin's own test wrapper. The fixtures are set up on the host,
    like for any other cooperative test. The body is not awaited here: it is sent to the
    container with its fixture values, and awaited from a thread. The other cooperative
    tests keep running meanwhile. The item attributes and the teardowns are what the
    plugin uses for its durations and reporting.
    """
    marker = item.get_closest_marker("docker_playwright")
    timeout = (marker.kwargs.get("timeout") if marker else None) or DEFAULT_TIMEOUT
    function = item.function
    fixture_names = list(inspect.signature(function).parameters)

    # The cooperative plugin reads these attributes to report durations, like its own
    # test wrapper does
    report_item: Any = item
    report_item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    report_item.stop_setup = time.time()

    # Mismatched fixture names and values would call the remote body with the wrong
    # arguments. Fail immediately instead of silently dropping values
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
        await asyncio.to_thread(_run_in_container, function, item.name, kwargs, timeout)
    except BaseException:
        # Run the teardowns, otherwise fixtures may be left holding their locks
        report_item.stop = time.time()
        await do_teardowns()
        raise
    report_item.stop = time.time()
    await do_teardowns()


def install() -> None:
    """Make pytest-asyncio-cooperative run docker_playwright-marked tests remotely.

    It hooks into the same function the plugin uses for its hypothesis support. Marked
    tests are then collected, timed, torn down and reported like any other test.
    Called from the conftest when pytest starts.
    """
    from pytest_asyncio_cooperative import plugin as cooperative

    original_item_to_task = cooperative.item_to_task

    def item_to_task(item: pytest.Function):
        if "docker_playwright" in item.keywords:
            return _run_item(item)
        return original_item_to_task(item)

    cooperative.item_to_task = item_to_task
