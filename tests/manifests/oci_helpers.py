# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import os

import aiohttp


def load_docker_config():
    # Determine the path to config.json based on the OS
    docker_config_path = os.path.expanduser("~/.docker/config.json")

    if not os.path.exists(docker_config_path):
        raise FileNotFoundError(f"Docker config file not found at {docker_config_path}")

    with open(docker_config_path) as f:
        config = json.load(f)

    return config


def get_auth_header(registry):
    config = load_docker_config()
    auths = config.get("auths", {})

    # The registry URL in the config may or may NOT have the "https://" prefix
    registry_key = registry.replace("https://", "")
    auth_token = auths.get(registry_key)["auth"]

    if not auth_token:
        return ""
    # The auth token is base64-encoded "username:password"
    return f"Basic {auth_token}"


async def get_bearer_token(registry, repo, tag, service="registry.docker.io"):
    auth_header = get_auth_header(registry)

    # Trigger a 401 to get the auth challenge
    auth_url = f"https://{registry}/v2/{repo}/manifests/{tag}"
    headers = {
        "Accept": "application/vnd.oci.image.index.v1+json",
    }
    if auth_header:
        headers["Authorization"] = auth_header

    async with aiohttp.ClientSession() as session, session.get(auth_url, headers=headers) as response:
        if response.status == 200:
            return None
        if response.status != 401:
            raise Exception(f"Unexpected status code: {response.status}")

        # Extract realm and service from Www-Authenticate header
        auth_header = response.headers.get("Www-Authenticate", "")
        realm = auth_header.split('realm="')[1].split('"')[0]
        service = auth_header.split('service="')[1].split('"')[0] if 'service="' in auth_header else service

        # Request the token
        token_url = f"{realm}?service={service}&scope=repository:{repo}:pull"
        async with session.get(token_url) as token_response:
            token_response.raise_for_status()
            token_data = await token_response.json()
            return token_data["token"]


async def get_oci_image_source_ref(image_values: dict, platform_os="linux", platform_arch="amd64"):
    registry = image_values["registry"]
    repo = image_values["repository"]
    tag = image_values["tag"]

    index_url = f"https://{registry}/v2/{repo}/manifests/{tag}"

    # Get the bearer token
    token = await get_bearer_token(registry, repo, tag)
    if token:
        auth_header = {"Authorization": f"Bearer {token}"}
    # If no bearer token was issued, it means we are able to authenticate using basic auth
    elif get_auth_header(registry):
        auth_header = {"Authorization": get_auth_header(registry)}
    else:
        raise RuntimeError("Error: Unable to authenticate. Please check your Docker configuration.")

    # Step 1: Fetch the OCI image index
    async with (
        aiohttp.ClientSession() as session,
        session.get(index_url, headers={"Accept": "application/vnd.oci.image.index.v1+json"} | auth_header) as response,
    ):
        if response.status != 200:
            raise RuntimeError(f"Error: Could not fetch image index. Status code: {response.status}")

        index = await response.json()

        # Step 2: Find the manifest for the desired platform
        manifest_digest = None
        for manifest in index["manifests"]:
            if (
                manifest.get("platform", {}).get("os") == platform_os
                and manifest.get("platform", {}).get("architecture") == platform_arch
                and manifest.get("mediaType", "") == "application/vnd.oci.image.manifest.v1+json"
            ):
                manifest_digest = manifest["digest"]
                break

        if not manifest_digest:
            raise RuntimeError("Error: No matching manifest found for the specified platform.")

        # Step 3: Fetch the platform-specific manifest
        manifest_url = f"https://{registry}/v2/{repo}/manifests/{manifest_digest}"
        async with session.get(
            manifest_url, headers={"Accept": "application/vnd.oci.image.manifest.v1+json"} | auth_header
        ) as manifest_response:
            if manifest_response.status != 200:
                raise RuntimeError(
                    f"Error: Could not fetch manifest {manifest_url}. Status code: {manifest_response.status}"
                )

            manifest = await manifest_response.json()
            config_digest = manifest["config"]["digest"]

        # Step 4: Fetch the config blob
        config_url = f"https://{registry}/v2/{repo}/blobs/{config_digest}"
        async with session.get(
            config_url, headers={"Accept": "application/vnd.oci.image.manifest.v1+json"} | auth_header
        ) as config_response:
            if config_response.status != 200:
                raise RuntimeError(f"Error: Could not fetch config blob. Status code: {config_response.status}")

            result = await config_response.read()
            config = json.loads(result)
            annotations = config.get("config", {}).get("Labels", {})

            # Step 5: Extract source ref from annotations
            source_ref = annotations.get("org.opencontainers.image.revision") or annotations.get(
                "org.opencontainers.image.source"
            )

            return source_ref
