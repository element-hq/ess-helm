# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio

import pytest
from lightkube import AsyncClient

from .fixtures import ESSData, User
from .lib.utils import aiohttp_get_json, aiohttp_post_json, value_file_has


# This creates an unencrypted room, invites hookshot, creates a webhook,
# and verifies that hookshot posts webhook payloads to the room
@pytest.mark.skipif(not value_file_has("hookshot.enabled", True), reason="Hookshot not enabled")
@pytest.mark.parametrize("users", [(User(name="hookshot-user"),)], indirect=True)
@pytest.mark.asyncio_cooperative
async def test_hookshot_webhook(
    kube_client: AsyncClient,
    ingress_ready,
    generated_data: ESSData,
    users,
    ssl_context,
):
    await ingress_ready("hookshot")
    user_access_token = users[0].access_token
    hookshot_mxid = f"@hookshot:{generated_data.server_name}"
    # Create an unencrypted room
    create_room_request = {
        "name": "Hookshot webhook test",
        "preset": "private_chat",
        "visibility": "private",
    }

    create_room = await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/createRoom",
        create_room_request,
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    room_id = create_room["room_id"]

    # Invite hookshot to the room
    invite_request = {
        "user_id": hookshot_mxid,
    }

    await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/invite",
        invite_request,
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Wait for hookshot to join
    count = 0
    while count < 10:
        members_response = await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/members",
            {"Authorization": f"Bearer {user_access_token}"},
            ssl_context,
        )
        # Extract joined members from the membership events
        joined_members = [
            event["state_key"]
            for event in members_response.get("chunk", [])
            if event.get("content", {}).get("membership") == "join"
        ]
        if hookshot_mxid in joined_members:
            break
        else:
            await asyncio.sleep(3)
            count = count + 1

    assert hookshot_mxid in joined_members, f"Hookshot did not join the room : {json.dumps(members_response)}"

    # Generate a random webhook id
    webhook_id = f"{generated_data.server_name}-{create_room['room_id']}"
    webhook_command = {
        "msgtype": "m.text",
        "body": f"!hookshot webhook {webhook_id}",
    }

    await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/send/m.room.message",
        webhook_command,
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Wait for and extract webhook URL from hookshot's response
    webhook_url = None
    count = 0
    while count < 10:
        messages = await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/messages?dir=b&limit=10",
            {"Authorization": f"Bearer {user_access_token}"},
            ssl_context,
        )

        # Look for hookshot's response containing the webhook URL
        for event in messages.get("chunk", []):
            if event.get("sender") == hookshot_mxid and "body" in event.get("content", {}):
                body = event["content"]["body"]
                if "http" in body:
                    webhook_url = body
                    break

        if webhook_url:
            break
        else:
            await asyncio.sleep(3)
            count = count + 1

    assert webhook_url is not None, f"Failed to create webhook : {json.dumps(messages)}"

    # Send a test payload to the webhook
    test_payload = {
        "text": "Test webhook payload",
    }

    await aiohttp_post_json(
        webhook_url,
        test_payload,
        {},
        ssl_context,
    )

    # Wait for hookshot to post the payload to the room
    payload_found = False
    count = 0
    while count < 10:
        messages = await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/messages?dir=b&limit=20",
            {"Authorization": f"Bearer {user_access_token}"},
            ssl_context,
        )

        # Look for message from hookshot containing our payload
        for event in messages.get("chunk", []):
            if event.get("sender") == hookshot_mxid and "body" in event.get("content", {}):
                body = event["content"]["body"]
                if "Test webhook payload" in body:  # Adjust based on how hookshot formats messages
                    payload_found = True
                    break

        if payload_found:
            break
        else:
            await asyncio.sleep(3)
            count = count + 1

    assert payload_found, "Hookshot did not post webhook payload to room"

    return room_id
