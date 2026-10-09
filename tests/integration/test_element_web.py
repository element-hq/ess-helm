# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
from typing import TYPE_CHECKING

import pytest

from .fixtures import BrowserPages, ESSData, User, run_scenario_with_page_refresh
from .lib.matrix_authentication_service import login_on_mas_page
from .lib.utils import aiohttp_get_json, value_file_has

# Playwright is optional: it is installed by scripts/setup_playwright_controller.sh. When
# it is missing, the browser tests are skipped by the browser_pages fixture.
if TYPE_CHECKING:
    from playwright.async_api import Page


@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_web_can_access_config_json(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("element-web")

    json_content = await aiohttp_get_json(f"https://element.{generated_data.server_name}/config.json", {}, ssl_context)
    assert "some_key" in json_content
    assert json_content["some_key"]["some_value"] == f"https://test.{generated_data.server_name}"


@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_web_loads_in_browser(ingress_ready, generated_data: ESSData, browser_pages: BrowserPages):
    from playwright.async_api import expect

    async def scenario(page: "Page"):
        await ingress_ready("element-web")

        await page.goto(f"https://element.{generated_data.server_name}/")

        await expect(page).to_have_title(re.compile("Element"))

    await run_scenario_with_page_refresh(browser_pages, scenario)


@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("users", [[User("browser-element-web-user")]], indirect=True)
async def test_element_web_login_via_mas(
    ingress_ready, generated_data: ESSData, browser_pages: BrowserPages, users: list[User]
):
    from playwright.async_api import expect

    async def scenario(page: "Page"):
        await ingress_ready("element-web")
        await ingress_ready("matrix-authentication-service")

        await page.goto(f"https://element.{generated_data.server_name}/")
        await page.get_by_role("button", name="Continue").click()
        await page.wait_for_url(f"https://mas.{generated_data.server_name}/**")

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        await expect(page.get_by_role("heading")).to_contain_text("Continue to Element")
        await page.get_by_role("button", name="Continue").click()

        await page.wait_for_url(f"https://element.{generated_data.server_name}/**")

    await run_scenario_with_page_refresh(browser_pages, scenario)
