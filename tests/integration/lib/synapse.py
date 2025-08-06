# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import hmac
import mimetypes
from pathlib import Path
from ssl import SSLContext

import pytest

from .utils import KubeCtl, aiohttp_client, aiohttp_get_json, aiohttp_post_json


async def get_nonce(synapse_fqdn: str, ssl_context) -> str:
    """
    Call Synapse for a nonce.
    """
    response = await aiohttp_get_json(f"https://{synapse_fqdn}/_synapse/admin/v1/register", {}, ssl_context)
    return response.get("nonce", "")


def generate_mac(username: str, password: str, admin: bool, registration_shared_secret: str, nonce: str) -> str:
    """
    Generate a MAC for using in registering the user.
    """
    # From: https://github.com/element-hq/synapse/blob/master/docs/admin_api/register_api.md
    mac = hmac.new(
        key=registration_shared_secret.encode("utf8"),
        digestmod=hashlib.sha1,
    )

    mac.update(nonce.encode("utf8"))
    mac.update(b"\x00")
    mac.update(username.encode("utf8"))
    mac.update(b"\x00")
    mac.update(password.encode("utf8"))
    mac.update(b"\x00")
    mac.update(b"admin" if admin else b"notadmin")
    return mac.hexdigest()


async def create_synapse_user(
    synapse_fqdn: str,
    username: str,
    password: str,
    admin: bool,
    registration_shared_secret: str,
    ssl_context: SSLContext,
    pytestconfig: pytest.Config,
) -> str:
    """
    Create the user and return access_token
    """
    cached_user_token = pytestconfig.cache.get(f"ess-helm/cached-tokens/{username}", None)
    if cached_user_token:
        return cached_user_token

    nonce = await get_nonce(synapse_fqdn, ssl_context)
    mac = generate_mac(username, password, admin, registration_shared_secret, nonce)
    data = {
        "nonce": nonce,
        "username": username,
        "password": password,
        "admin": admin,
        "mac": mac,
    }
    response = await aiohttp_post_json(f"https://{synapse_fqdn}/_synapse/admin/v1/register", data, {}, ssl_context)
    pytestconfig.cache.set(f"ess-helm/cached-tokens/{username}", response["access_token"])
    return response["access_token"]


async def upload_media(synapse_fqdn: str, user_access_token: str, file_path: Path, ssl_context: SSLContext):
    headers = {}
    headers["Authorization"] = f"Bearer {user_access_token}"
    headers["Host"] = synapse_fqdn

    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    params = {"filename": file_path.name}

    with open(file_path, "rb") as f:
        async with (
            aiohttp_client(ssl_context) as client,
            client.post(
                "https://127.0.0.1/_matrix/media/v3/upload",
                server_hostname=synapse_fqdn,
                headers=headers,
                params=params,
                data=f.read(),
            ) as response,
        ):
            response_json = await response.json()

            assert response_json["content_uri"].startswith("mxc://")

            return response_json


async def download_media(
    server_name: str, synapse_fqdn: str, user_access_token, content_upload_json: dict, ssl_context: SSLContext
):
    headers = {}
    headers["Authorization"] = f"Bearer {user_access_token}"
    headers["Host"] = synapse_fqdn
    content_id = content_upload_json["content_uri"].replace(f"mxc://{server_name}/", "")

    # Initialize SHA-256 hasher
    sha256_hash = hashlib.sha256()
    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            f"https://127.0.0.1/_matrix/client/v1/media/download/{server_name}/{content_id}",
            headers=headers,
            server_hostname=synapse_fqdn,
        ) as response,
    ):
        # Process the stream in chunks
        while True:
            chunk = await response.content.read(8192)  # 8KB chunks
            if not chunk:
                break
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


async def assert_downloaded_content(
    kubectl: KubeCtl, media_pod, namespace, source_sha256, content_id, content_download_sha256
):
    assert source_sha256 == content_download_sha256.split(" ")[0]

    # Look in Synapse's short-term disk storage for the file
    path = f"local_content/{content_id[0:2]}/{content_id[2:4]}/{content_id[4:]}"
    local_path = f"/media/media_store/{path}"

    local_media_sha256 = await kubectl.exec(media_pod, namespace, ["sha256sum", local_path])
    assert source_sha256 == local_media_sha256.split(" ")[0]
