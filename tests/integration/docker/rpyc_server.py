# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""rpyc server running as the main process of the playwright test container.

The docker_playwright decorator connects to it for the whole pytest session and calls
`run` once per test, with the test function and its fixture values cloudpickled by the
host. It never runs on the pytest host. It only listens on the loopback interface, which
the container shares with the host network.
"""

import asyncio
import contextlib
import io
import sys
import traceback
from typing import Any

import cloudpickle
import rpyc


class DockerPlaywrightService(rpyc.Service):
    """Runs the cloudpickled test bodies the host sends, one `run` call per test"""

    def exposed_run(self, payload: bytes) -> str:
        """Run one cloudpickled test body; returns its captured output.

        Raises with the output and the traceback if it fails, so that the host can
        report both.
        """
        data: dict[str, Any] = cloudpickle.loads(payload)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                asyncio.run(asyncio.wait_for(data["func"](**data["kwargs"]), timeout=data["timeout"]))
            except BaseException:
                raise RuntimeError(f"{output.getvalue()}\n{traceback.format_exc()}") from None
        return output.getvalue()


def main() -> None:
    server = rpyc.ThreadedServer(DockerPlaywrightService, hostname="127.0.0.1", port=int(sys.argv[1]))
    server.start()


if __name__ == "__main__":
    main()
