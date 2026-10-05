# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from .fixtures import ESSData, User
from .lib.utils import aiohttp_get_json, value_file_has, wait_for_ingress


@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.asyncio_cooperative
async def test_element_web_can_access_config_json(ingress_ready, generated_data: ESSData, ssl_context):
    await ingress_ready("element-web")

    json_content = await aiohttp_get_json(f"https://element.{generated_data.server_name}/config.json", {}, ssl_context)
    assert "some_key" in json_content
    assert json_content["some_key"]["some_value"] == f"https://test.{generated_data.server_name}"


# Runs inside the playwright container, as the host may not be able to run a browser (e.g. Alpine)
@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.asyncio_cooperative
@pytest.mark.docker_playwright
async def test_element_web_loads_in_browser(generated_data: ESSData):
    # Imported here: playwright is only installed inside the test container
    from playwright.async_api import expect

    from .lib.browser import browser_page

    await wait_for_ingress(f"element.{generated_data.server_name}", generated_data._root_ca.cert_as_pem())

    async with browser_page() as page:
        await page.goto(f"https://element.{generated_data.server_name}/")

        await expect(page).to_have_title(re.compile("Element"))


# Runs inside the playwright container, as the host may not be able to run a browser (e.g. Alpine)
@pytest.mark.skipif(value_file_has("elementWeb.enabled", False), reason="ElementWeb not deployed")
@pytest.mark.skipif(value_file_has("matrixAuthenticationService.enabled", False), reason="MAS not deployed")
@pytest.mark.parametrize("users", [[User("browser-element-web-user")]], indirect=True)
@pytest.mark.asyncio_cooperative
@pytest.mark.docker_playwright
async def test_element_web_login_via_mas(generated_data: ESSData, users: list[User]):
    # Imported here: playwright is only installed inside the test container
    from playwright.async_api import expect

    from .lib.browser import browser_page, login_on_mas_page

    await wait_for_ingress(f"element.{generated_data.server_name}", generated_data._root_ca.cert_as_pem())

    async with browser_page() as page:
        await page.goto(f"https://element.{generated_data.server_name}/")
        await page.get_by_role("button", name="Continue").click()
        await page.wait_for_url(f"https://mas.{generated_data.server_name}/**")

        await login_on_mas_page(page, users[0].name, generated_data.secrets_random)

        await expect(page.get_by_role("heading")).to_contain_text("Continue to Element")
        await page.get_by_role("button", name="Continue").click()

        await page.wait_for_url(f"https://element.{generated_data.server_name}/**")
