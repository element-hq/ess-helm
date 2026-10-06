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

from playwright.async_api import Page, async_playwright

CA_NICKNAME = "ess-helm-test-ca"
_installed_cas: set[str] = set()
# Tests run concurrently in the test container: concurrent certutil invocations on the
# same NSS database would race, so the installations are serialized
_install_lock = threading.Lock()


async def _browser_trust_ca(ca_pem: str) -> None:
    """Install ca_pem in the trust store the browser reads, so that it validates the
    certificates it is served. No-op if it is already installed.

    Chromium has no option to hand it a CA, and it does not read the system trust store:
    on Linux it trusts the locally-managed roots of the NSS database in ~/.pki/nssdb.
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
            # Creating an already existing database fails, and so does dropping an entry that is
            # not there; both are fine to ignore. Importing a nickname that exists duplicates it,
            # so any previous entry with ours is dropped first.
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

    The certificates served by the ingress are signed by the test CA, which ca_pem holds:
    it is installed in the browser's trust store so that they are actually validated.
    Chromium resolves *.localhost to the loopback address itself, which is where the
    ingress proxy listens.
    """
    await _browser_trust_ca(ca_pem)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            context = await browser.new_context()
            page = await context.new_page()
            yield page
        finally:
            await browser.close()


async def login_on_mas_page(page: Page, username: str, password: str):
    """Fill and submit the MAS password login form the page is currently showing"""
    await page.get_by_role("textbox", name="Username").fill(username)
    await page.get_by_role("textbox", name="Password").fill(password)
    await page.get_by_role("button", name="Continue").click()
