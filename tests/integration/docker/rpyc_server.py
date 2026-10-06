# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""rpyc server running as the main process of the playwright test container.

The docker_playwright decorator opens a connection to it per test and calls `run` with the
test function and its fixture values cloudpickled by the host. Each connection is served
in its own thread, so test bodies run concurrently; their stdout and stderr are captured
per thread. It never runs on the pytest host. It only listens on the loopback interface,
which the container shares with the host network.
"""

import asyncio
import io
import sys
import threading
import traceback
from typing import Any, TextIO

import cloudpickle
import rpyc

_local = threading.local()


class _RunOutput(io.TextIOBase):
    """A stdout/stderr that routes the writes of each thread to the buffer of the run
    happening on it, so that concurrent runs each capture their own output. Threads not
    running a test, e.g. the server's own, keep writing to the original stream.
    """

    def __init__(self, stream: TextIO):
        self._stream = stream

    def write(self, text: str) -> int:
        (getattr(_local, "buffer", None) or self._stream).write(text)
        return len(text)

    def flush(self) -> None:
        pass


class DockerPlaywrightService(rpyc.Service):
    """Runs the cloudpickled test bodies the host sends, one `run` call per connection"""

    def exposed_run(self, payload: bytes) -> tuple[str, str | None, tuple[bytes, ...]]:
        """Run one cloudpickled test body; returns its captured output.

        Also returns the traceback, and the traces recorded of the failing test's browser
        contexts (see integration.lib.browser.pop_failure_traces), for the host to report
        and export: it cannot read files inside the container. The traces are a tuple so
        that the whole return value travels by value over rpyc, and stays readable once
        the connection is closed.
        """
        data: dict[str, Any] = cloudpickle.loads(payload)
        output = io.StringIO()
        _local.buffer = output
        # Imported here: browser imports playwright, which the pytest host does not have
        from integration.lib.browser import pop_failure_traces

        try:
            asyncio.run(asyncio.wait_for(data["func"](**data["kwargs"]), timeout=data["timeout"]))
            error = None
        except BaseException:
            error = f"{output.getvalue()}\n{traceback.format_exc()}"
        finally:
            # Pop the traces of the browser contexts the test had open: they are returned
            # with the failure, or discarded if it passed (e.g. it swallowed a failure
            # itself, which must not be attributed to a later run on the same thread)
            traces = pop_failure_traces()
            _local.buffer = None
        return (output.getvalue(), error, tuple(traces))


def main() -> None:
    sys.stdout = _RunOutput(sys.stdout)
    sys.stderr = _RunOutput(sys.stderr)
    server = rpyc.ThreadedServer(DockerPlaywrightService, hostname="127.0.0.1", port=int(sys.argv[1]))
    server.start()


if __name__ == "__main__":
    main()
