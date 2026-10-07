# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from .artifacts import CertKey
from .fixtures import ESSData, User
from .lib.utils import aiohttp_client, value_file_has


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


# Runs inside the playwright container, because the host may not be able to run a browser (e.g. Alpine)
@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.parametrize("users", [[User("browser-admin-user", admin=True)]], indirect=True)
@pytest.mark.parametrize("ingress_ready_for", ["element-admin"], indirect=True)
@pytest.mark.asyncio_cooperative
@pytest.mark.docker_playwright
async def test_element_admin_login(generated_data: ESSData, users: list[User], root_ca: CertKey, ingress_ready_for):
    # Imported here: playwright is only installed inside the test container
    from playwright.async_api import expect

    from .lib.browser import browser_page, login_on_mas_page

    async with browser_page(generated_data._root_ca.cert_as_pem()) as page:
        await page.goto(f"https://admin.{generated_data.server_name}/")
        await page.get_by_role("button", name="Get started").click()

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        await expect(page.get_by_role("heading")).to_contain_text("Continue to Element Admin")
        await page.get_by_role("button", name="Continue").click()

        await expect(page).to_have_title(f"Dashboard • {generated_data.server_name} • Element Admin")


# Runs inside the playwright container, because the host may not be able to run a browser (e.g. Alpine)
@pytest.mark.skipif(value_file_has("elementAdmin.enabled", False), reason="elementAdmin not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.parametrize("users", [[User("browser-non-admin-user")]], indirect=True)
@pytest.mark.parametrize("ingress_ready_for", ["element-admin"], indirect=True)
@pytest.mark.asyncio_cooperative
@pytest.mark.docker_playwright
async def test_element_admin_login_rejects_non_admin(
    generated_data: ESSData, users: list[User], root_ca: CertKey, ingress_ready_for
):
    # Imported here: playwright is only installed inside the test container
    from playwright.async_api import expect

    from .lib.browser import browser_page, login_on_mas_page

    async with browser_page(root_ca.cert_bundle_as_pem()) as page:
        await page.goto(f"https://admin.{generated_data.server_name}/")
        await page.get_by_role("button", name="Get started").click()

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        # The user can be rejected in two places: by MAS, or by Element Admin after the OAuth login flow
        await expect(page.get_by_role("heading")).to_contain_text(
            re.compile("Administrator access required|The authorization request was denied by the policy")
        )
