# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Browser helpers for the tests that run inside the docker_playwright test container.

This module imports playwright, which is only installed inside the test container. It must
not be imported from code that runs on the pytest host, or from fixtures.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from playwright.async_api import Page, async_playwright


@asynccontextmanager
async def browser_page() -> AsyncGenerator[Page]:
    """A playwright chromium page to run a browser scenario with.

    The test CA isn't in the browser's trust store, so certificate validation is skipped.
    Chromium resolves *.localhost to the loopback address itself, which is where the
    ingress proxy listens.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            yield page
        finally:
            await browser.close()


async def login_on_mas_page(page: Page, username: str, password: str):
    """Fill and submit the MAS password login form the page is currently showing"""
    await page.get_by_role("textbox", name="Username").fill(username)
    await page.get_by_role("textbox", name="Password").fill(password)
    await page.get_by_role("button", name="Continue").click()
