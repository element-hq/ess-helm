# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from ssl import SSLContext
from urllib.parse import urlparse

import aiohttp
from aiohttp_retry import RetryClient

from ..fixtures import ESSData
from .utils import aiohttp_post_json, retry_options


async def get_client_token(mas_fqdn: str, generated_data: ESSData, ssl_context: SSLContext) -> str:
    client_credentials_data = {"grant_type": "client_credentials", "scope": "urn:mas:admin urn:mas:graphql:*"}
    url = f"https://{mas_fqdn}/oauth2/token"
    host = urlparse(url).hostname
    if not host:
        raise ValueError(f"{url} does not have a hostname")

    async with (
        aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session,
        RetryClient(session, retry_options=retry_options, raise_for_status=True) as retry,
        retry.post(
            url.replace(host, "127.0.0.1"),
            headers={"Host": host},
            server_hostname=host,
            data=client_credentials_data,
            auth=aiohttp.BasicAuth("000000000000000PYTESTADM1N", generated_data.mas_oidc_client_secret),
        ) as response,
    ):
        return (await response.json())["access_token"]


async def create_mas_user(
    mas_fqdn: str,
    username: str,
    password: str,
    admin: bool,
    bearer_token: str,
    ssl_context: SSLContext,
) -> str:
    """
    Create the user and return their user id
    """
    create_user_data = {"username": username}
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/api/admin/v1/users", headers=headers, data=create_user_data, ssl_context=ssl_context
    )
    user_id = response["data"]["id"]

    set_password_data = {"password": password, "skip_password_check": True}

    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/api/admin/v1/users/{user_id}/set-password",
        headers=headers,
        data=set_password_data,
        ssl_context=ssl_context,
    )

    set_admin_data = {"admin": admin}

    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/api/admin/v1/users/{user_id}/set-admin",
        headers=headers,
        data=set_admin_data,
        ssl_context=ssl_context,
    )

    check_user_query = """
        query UserByUsername($username: String!) {
          userByUsername(username: $username) {
              id lockedAt
          }
        }
    """
    check_user_data = {"query": check_user_query, "variables": {"username": username}}

    headers = {"Authorization": f"Bearer {bearer_token}"}

    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/graphql", headers=headers, data=check_user_data, ssl_context=ssl_context
    )
    graphql_user_id = response["data"]["userByUsername"]["id"]

    create_session_mutation = """
        mutation CreateOauth2Session($userId: String!, $scope: String!) {
            createOauth2Session(input: { userId: $userId, permanent: true, scope: $scope }) {
                accessToken
            }
        }
    """
    scopes = [
        "urn:matrix:org.matrix.msc2967.client:api:*",
    ]
    add_access_token_data = {
        "query": create_session_mutation,
        "variables": {"userId": graphql_user_id, "scope": " ".join(scopes)},
    }

    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/graphql", headers=headers, data=add_access_token_data, ssl_context=ssl_context
    )
    return response["data"]["createOauth2Session"]["accessToken"]
