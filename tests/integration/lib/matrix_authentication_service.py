# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from ssl import SSLContext
from urllib.parse import urlparse

import aiohttp
import pytest
from aiohttp_retry import RetryClient

from ..fixtures import ESSData
from .utils import aiohttp_get_json, aiohttp_post_json, retry_options


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
    synapse_fqdn: str,
    username: str,
    password: str,
    admin: bool,
    bearer_token: str,
    ssl_context: SSLContext,
    pytestconfig: pytest.Config,
) -> str:
    """
    Create the user and return their access token
    """
    cached_user_token = pytestconfig.cache.get(f"ess-helm/cached-tokens/{username}", None)
    if cached_user_token:
        # Locally the cached token may be from a previous run but we don't know whether it is with the same DB or not
        # We still want the caching in-case we request this for the same user multiple times in the same run
        try:
            headers = {"Authorization": f"Bearer {cached_user_token}"}
            response = await aiohttp_get_json(
                f"https://{synapse_fqdn}/_matrix/client/v3/account/whoami", headers=headers, ssl_context=ssl_context
            )
            if response["user_id"].split(":")[0] == f"@{username}":
                return cached_user_token
        except aiohttp.ClientResponseError:
            pass

        pytestconfig.cache.set(f"ess-helm/cached-tokens/{username}", None)

    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        response = await aiohttp_get_json(
            f"https://{mas_fqdn}/api/admin/v1/users/by-username/{username}", headers=headers, ssl_context=ssl_context
        )
    except aiohttp.ClientResponseError:
        create_user_data = {"username": username}
        response = await aiohttp_post_json(
            f"https://{mas_fqdn}/api/admin/v1/users", headers=headers, data=create_user_data, ssl_context=ssl_context
        )
    user_id = response["data"]["id"]

    response = await aiohttp_get_json(
        f"https://{mas_fqdn}/api/admin/v1/site-config", headers=headers, ssl_context=ssl_context
    )
    if response["password_login_enabled"]:
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
    if admin:
        scopes.append("urn:synapse:admin:*")
    add_access_token_data = {
        "query": create_session_mutation,
        "variables": {"userId": graphql_user_id, "scope": " ".join(scopes)},
    }

    response = await aiohttp_post_json(
        f"https://{mas_fqdn}/graphql", headers=headers, data=add_access_token_data, ssl_context=ssl_context
    )
    pytestconfig.cache.set(f"ess-helm/cached-tokens/{username}", response["data"]["createOauth2Session"]["accessToken"])
    return response["data"]["createOauth2Session"]["accessToken"]
