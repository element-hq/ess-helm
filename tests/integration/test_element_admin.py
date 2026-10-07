# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


# Annotations are stored as text and not evaluated when this file is imported.
# This allows the type-checking-only `Page` import below, even when playwright is missing.
# Python 3.14 behaves like this by default; this is a backport for older versions.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .fixtures import ESSData, User
from .lib.matrix_authentication_service import login_on_mas_page
from .lib.utils import aiohttp_client, value_file_has

# Playwright is optional: it is installed by scripts/setup_playwright_controller.sh. When
# it is missing, the browser tests are skipped by the browser_page fixture.
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
async def test_element_admin_login(ingress_ready, generated_data: ESSData, browser_page: Page, users: list[User]):
    from playwright.async_api import expect

    await ingress_ready("element-admin")
    await ingress_ready("matrix-authentication-service")

    await browser_page.goto(f"https://admin.{generated_data.server_name}/")
    await browser_page.get_by_role("button", name="Get started").click()

    await login_on_mas_page(browser_page, users[0].name, generated_data.secrets_random)

    await expect(browser_page.get_by_role("heading")).to_contain_text("Continue to Element Admin")
    await browser_page.get_by_role("button", name="Continue").click()

    await expect(browser_page).to_have_title(f"Dashboard • {generated_data.server_name} • Element Admin")


@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("users", [[User("browser-non-admin-user")]], indirect=True)
async def test_element_admin_login_rejects_non_admin(
    ingress_ready, generated_data: ESSData, browser_page: Page, users: list[User]
):
    from playwright.async_api import expect

    await ingress_ready("element-admin")
    await ingress_ready("matrix-authentication-service")

    await browser_page.goto(f"https://admin.{generated_data.server_name}/")
    await browser_page.get_by_role("button", name="Get started").click()

    await login_on_mas_page(browser_page, users[0].name, generated_data.secrets_random)

    await expect(browser_page.get_by_role("heading")).to_contain_text("Administrator access required")
