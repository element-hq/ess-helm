# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from playwright.async_api import Browser, async_playwright


@pytest.fixture(scope="session")
async def browser():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        yield browser
        await browser.close()


@pytest.fixture
async def browser_page(browser: Browser, proxy_server: str):
    # The test CA isn't in the browser's trust store, so certificate validation is skipped.
    # proxy_server routes *.localhost to the loopback address, where the ingress listens.
    context = await browser.new_context(proxy={"server": proxy_server}, ignore_https_errors=True)
    page = await context.new_page()
    yield page
    await context.close()
