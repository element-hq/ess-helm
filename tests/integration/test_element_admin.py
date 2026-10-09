# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import TYPE_CHECKING

import pytest

from .fixtures import BrowserPages, ESSData, User, run_scenario_with_page_refresh
from .lib.matrix_authentication_service import login_on_mas_page
from .lib.utils import aiohttp_client, value_file_has

# Playwright is optional: it is installed by scripts/setup_playwright_controller.sh. When
# it is missing, the browser tests are skipped by the browser_pages fixture.
if TYPE_CHECKING:
    from playwright.async_api import Page


@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_admin_can_access_root(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("element-admin")

    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            "https://127.0.0.1/",
            headers={"Host": f"admin.{generated_data.server_name}"},
            server_hostname=f"admin.{generated_data.server_name}",
        ) as response,
    ):
        assert response.status == 200


@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("users", [[User("browser-admin-user", admin=True)]], indirect=True)
async def test_element_admin_login(
    ingress_ready, generated_data: ESSData, browser_pages: BrowserPages, users: list[User]
):
    from playwright.async_api import expect

    async def scenario(page: "Page"):
        await ingress_ready("element-admin")
        await ingress_ready("matrix-authentication-service")

        await page.goto(f"https://admin.{generated_data.server_name}/")
        await page.get_by_role("button", name="Get started").click()

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        await expect(page.get_by_role("heading")).to_contain_text("Continue to Element Admin")
        await page.get_by_role("button", name="Continue").click()

        await expect(page).to_have_title(f"Dashboard • {generated_data.server_name} • Element Admin")

    await run_scenario_with_page_refresh(browser_pages, scenario)


@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("users", [[User("browser-non-admin-user")]], indirect=True)
async def test_element_admin_login_rejects_non_admin(
    ingress_ready, generated_data: ESSData, browser_pages: BrowserPages, users: list[User]
):
    from playwright.async_api import expect

    async def scenario(page: "Page"):
        await ingress_ready("element-admin")
        await ingress_ready("matrix-authentication-service")

        await page.goto(f"https://admin.{generated_data.server_name}/")
        await page.get_by_role("button", name="Get started").click()

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        await expect(page.get_by_role("heading")).to_contain_text("Administrator access required")

    await run_scenario_with_page_refresh(browser_pages, scenario)
