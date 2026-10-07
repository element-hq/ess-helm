# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""rpyc server running as the main process of the playwright test container.

For each test, the docker_playwright decorator opens a connection to this server. It
calls `run` with the test function and its fixture values, serialized with cloudpickle
by the host. Each connection runs in its own thread. Test bodies can therefore run at
the same time. The text each one writes to stdout and stderr is kept per thread.
This server never runs on the pytest host. It only listens on localhost, which the
container shares with the host network.
"""

import asyncio
import importlib
import io
import pkgutil
import sys
import threading
import traceback
from typing import Any, TextIO

import cloudpickle
import integration
import rpyc

_local = threading.local()


class _RunOutput(io.TextIOBase):
    """A replacement for stdout/stderr. Each thread writes to the buffer of the test
    running on it. Tests running at the same time therefore capture separate output.
    Threads not running a test, e.g. the server's own, write to the original stream.
    """

    def __init__(self, stream: TextIO):
        self._stream = stream

    def write(self, text: str) -> int:
        (getattr(_local, "buffer", None) or self._stream).write(text)
        return len(text)

    def flush(self) -> None:
        pass


class DockerPlaywrightService(rpyc.Service):
    """Runs the test bodies the host sends, one `run` call per connection"""

    def exposed_run(self, payload: bytes) -> tuple[str, str | None, tuple[bytes, ...]]:
        """Run one test body (from its cloudpickle payload). Returns the text it printed.

        If the test failed, also returns its traceback and the traces of the browser
        contexts it had open (see integration.lib.browser.pop_failure_traces). The host
        saves these traces itself: it cannot read files inside the container. The traces
        are a tuple, so rpyc copies the whole return value to the host. Remote
        references would stop working after the connection is closed.
        """
        data: dict[str, Any] = cloudpickle.loads(payload)
        output = io.StringIO()
        _local.buffer = output
        # Imported here: importing browser also imports playwright, which the pytest
        # host does not have installed
        from integration.lib.browser import pop_failure_traces

        try:
            asyncio.run(asyncio.wait_for(data["func"](**data["kwargs"]), timeout=data["timeout"]))
            error = None
        except BaseException:
            error = f"{output.getvalue()}\n{traceback.format_exc()}"
        finally:
            # Take out the traces of the browser contexts the test had open. They are
            # returned with the failure, or thrown away if the test passed. A test can
            # also catch and ignore a failure itself. Its traces must not be reported
            # for a later test on the same thread.
            traces = pop_failure_traces()
            _local.buffer = None
        return (output.getvalue(), error, tuple(traces))


def _import_test_package() -> None:
    """Import every module of the test package, before the server handles any connection.

    Reading a cloudpickle payload imports modules of the classes it refers to. Test
    bodies import more modules while they run (e.g. integration.lib.browser). Each
    connection runs on its own thread. If several threads import the same package for
    the first time at once, Python's import system can deadlock. This happens for a
    package whose __init__ imports its submodules, e.g. integration.fixtures.
    Importing everything up front, from a single thread, avoids that.
    """
    for module_info in pkgutil.walk_packages(integration.__path__, f"{integration.__name__}."):
        importlib.import_module(module_info.name)


def main() -> None:
    _import_test_package()
    sys.stdout = _RunOutput(sys.stdout)
    sys.stderr = _RunOutput(sys.stderr)
    server = rpyc.ThreadedServer(DockerPlaywrightService, hostname="127.0.0.1", port=int(sys.argv[1]))
    server.start()


if __name__ == "__main__":
    main()
