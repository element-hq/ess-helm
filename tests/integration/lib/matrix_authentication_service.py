# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

import base64
from ssl import SSLContext
from urllib.parse import urlparse

import aiohttp
from aiohttp_retry import RetryClient
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Secret

from ..fixtures import ESSData
from .utils import aiohttp_post_json, retry_options


async def get_mas_client_credentials(kube_client: AsyncClient, generated_data: ESSData):
  generated_secret = await kube_client.get(Secret, name=f"{generated_data.release_name}-generated",
                                           namespace=generated_data.ess_namespace)
  client_id = "0000000000000000000SYNAPSE"
  client_secret = base64.b64decode(generated_secret.data["MAS_SYNAPSE_OIDC_CLIENT_SECRET"]).decode("utf-8")
  return client_id, client_secret


async def get_client_token(client_id: str, client_secret: str, mas_fqdn: str,
                                 generated_data: ESSData, ssl_context: SSLContext) -> str:
    client_credentials_data = {"grant_type": "client_credentials", "scope": "urn:mas:admin urn:mas:graphql:*"}
    url = f"https://{mas_fqdn}/oauth2/token"
    host = urlparse(url).hostname

    async with (
        aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session,
        RetryClient(session, retry_options=retry_options, raise_for_status=True) as retry,
        retry.post(
            url.replace(host, "127.0.0.1"), headers={"Host": host}, server_hostname=host,
            params=client_credentials_data,
            auth=aiohttp.BasicAuth(client_id, client_secret),
        ) as response,
    ):
        return await response.json()["access_token"]


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
        f"{mas_fqdn}/api/admin/v1/users", headers=headers, data=create_user_data, ssl_context=ssl_context
    )
    user_id = response["data"]["id"]

    set_password_data = {"password": password, "skip_password_check": True}

    response = await aiohttp_post_json(
        f"{mas_fqdn}/api/admin/v1/users/{user_id}/set-password", headers=headers, data=set_password_data,
        ssl_context=ssl_context
    )

    set_admin_data = {"admin": admin}

    response = await aiohttp_post_json(
        f"{mas_fqdn}/api/admin/v1/users/{user_id}/set-admin", headers=headers, data=set_admin_data,
        ssl_context=ssl_context
    )

    create_session_mutation = """
        mutation CreateOauth2Session($userId: String!, $scope: String!) {
            createOauth2Session(input: { userId: $userId, permanent: true, scope: $scope }) {
                accessToken
            }
        }
    """
    scopes = ["urn:matrix:org.matrix.msc2967.client:api:*",]
    add_access_token_data ={"query": create_session_mutation,
                            "variables": {"userId": user_id, "scope": " ".join(scopes)}}

    response = await aiohttp_post_json(
        f"{mas_fqdn}/graphql", headers=headers, data=add_access_token_data,
        ssl_context=ssl_context
    )
    return response["data"]["createOauth2Session"]["accessToken"]
