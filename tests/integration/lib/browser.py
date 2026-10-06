# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Browser helpers for the tests that run inside the docker_playwright test container.

This module imports playwright, which is only installed inside the test container. It must
not be imported from code that runs on the pytest host, or from fixtures.
"""

import asyncio
import subprocess
import tempfile
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

CA_NICKNAME = "ess-helm-test-ca"
_installed_cas: set[str] = set()
# Tests run at the same time in the test container. certutil commands on the same NSS
# database would conflict, so installations are run one after the other
_install_lock = threading.Lock()

# The traces recorded for the browser contexts a failing test had open, stored per
# thread id. The rpyc server runs each test in its own thread. It takes out the traces
# its test recorded and sends them to the host, which cannot read files inside the
# container
_failure_traces: dict[int, list[bytes]] = {}


def pop_failure_traces() -> list[bytes]:
    """Return and delete the failure traces of the test that ran on the calling thread.
    Returns an empty list if there are none.
    """
    return _failure_traces.pop(threading.get_ident(), [])


async def _record_failure_trace(context: BrowserContext) -> None:
    """Record a trace of context, for pop_failure_traces to return it to the host.

    Never fail here. The failure being handled may have stopped the browser too. There
    is then no trace to record, and the original failure must not be hidden by a new
    error.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip") as trace_file:
            await context.tracing.stop(path=trace_file.name)
            _failure_traces.setdefault(threading.get_ident(), []).append(Path(trace_file.name).read_bytes())
    except Exception:
        return


async def _browser_trust_ca(ca_pem: str) -> None:
    """Install ca_pem in the trust store the browser reads. The browser then accepts
    the certificates it is served. Does nothing if it is already installed.

    Chromium has no option to be given a CA. It also does not read the system trust
    store: on Linux, it reads the CAs it manages itself from the NSS database in
    ~/.pki/nssdb.
    """
    if ca_pem in _installed_cas:
        return

    def _trust_ca(ca_pem: str) -> None:
        with _install_lock:
            if ca_pem in _installed_cas:
                return
            nssdb = Path.home() / ".pki" / "nssdb"
            nssdb.mkdir(parents=True, exist_ok=True)
            database = f"sql:{nssdb}"
            # Creating an existing database fails. Deleting an entry that does not
            # exist fails too. Both failures are fine to ignore. Importing a name that
            # already exists would create a duplicate, so any old entry with our name
            # is deleted first
            subprocess.run(["certutil", "-N", "--empty-password", "-d", database], capture_output=True)
            subprocess.run(["certutil", "-D", "-d", database, "-n", CA_NICKNAME], capture_output=True)
            with tempfile.NamedTemporaryFile("w", suffix=".pem") as ca_file:
                ca_file.write(ca_pem)
                ca_file.flush()
                subprocess.run(
                    ["certutil", "-A", "-t", "C,,", "-n", CA_NICKNAME, "-d", database, "-i", ca_file.name],
                    check=True,
                    capture_output=True,
                )
            _installed_cas.add(ca_pem)

    await asyncio.to_thread(_trust_ca, ca_pem)


@asynccontextmanager
async def browser_page(ca_pem: str) -> AsyncGenerator[Page]:
    """A playwright chromium page to run a browser scenario with.

    The certificates served by the ingress are signed by the test CA. ca_pem holds the
    CA in PEM form. It is installed in the browser's trust store, so the browser
    accepts them. Chromium itself resolves *.localhost to the localhost address, where
    the ingress proxy listens.

    Everything the page does is traced. If the test body fails, the trace is recorded
    for the host to save (see pop_failure_traces). It can be opened in the playwright
    trace viewer, with screenshots and DOM snapshots.
    """
    await _browser_trust_ca(ca_pem)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            context = await browser.new_context()
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = await context.new_page()
            try:
                yield page
            except BaseException:
                # Record the trace and stop tracing; on success, tracing is stopped and
                # the trace is thrown away
                await _record_failure_trace(context)
                raise
            else:
                await context.tracing.stop()
        finally:
            await browser.close()


async def login_on_mas_page(page: Page, username: str, password: str):
    """Fill and submit the MAS password login form the page is currently showing"""
    await page.get_by_role("textbox", name="Username").fill(username)
    await page.get_by_role("textbox", name="Password").fill(password)
    await page.get_by_role("button", name="Continue").click()
