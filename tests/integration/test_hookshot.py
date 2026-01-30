# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
import os
import time
from urllib.parse import urlparse

import pytest
import semver
from lightkube import AsyncClient

from .fixtures import ESSData, User
from .lib.utils import aiohttp_client, aiohttp_get_json, aiohttp_post_json, aiohttp_put_json, value_file_has


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
    await ingress_ready("synapse")
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

    # Get current power levels
    power_levels = await aiohttp_get_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels",
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Promote hookshot to moderator (power level 50)
    if "users" not in power_levels:
        power_levels["users"] = {}

    power_levels["users"][hookshot_mxid] = 50

    await aiohttp_put_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels",
        power_levels,
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Generate a random webhook id
    webhook_id = f"{generated_data.server_name}-{create_room['room_id'][1:].split(':')[0]}"
    webhook_command = {
        "msgtype": "m.text",
        "body": f"!hookshot webhook {webhook_id}",
    }
    webhook_create_ts = int(time.time() * 1000)

    await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{room_id}/send/m.room.message",
        webhook_command,
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Wait for hookshot to send an invite to the admin room
    admin_room_id = None
    count = 0
    next_batch = None

    # This finds the admin room either from the joined state or from the invite state
    def _find_admin_room_in_room_data(rooms: dict):
        admin_room_id = None
        for room, room_data in rooms.items():
            join_state = room_data.get("timeline", {}).get("events", []) + room_data.get("state", {}).get("events", [])
            invite_state = room_data.get("invite_state", {}).get("events", [])
            # Check if one of the room is created by hookshot
            for state_events in join_state:
                # This assumes that the admin room is the only room created by hookshot in our test suite
                if state_events.get("sender") == hookshot_mxid and state_events.get("type") == "m.room.create":
                    admin_room_id = room
                    break
            else:
                # Check if the invite is from hookshot
                for event in invite_state:
                    # This assumes that the admin room is the only room created by hookshot in our test suite
                    if event.get("sender") == hookshot_mxid and event.get("type") == "m.room.member":
                        admin_room_id = room
                        break
        return admin_room_id

    while count < 10:
        # Sync to get invited rooms
        sync_args = f"since={next_batch}" if next_batch else "full_state=true"
        sync_response = await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/v3/sync?{sync_args}&timeout=1000",
            {"Authorization": f"Bearer {user_access_token}"},
            ssl_context,
        )

        if sync_response.get("next_batch"):
            next_batch = sync_response.get("next_batch")

        # Check for joined rooms, if hookshot already invited the user to the admin room
        joined_rooms: dict = sync_response.get("rooms", {}).get("join", {})
        invited_rooms: dict = sync_response.get("rooms", {}).get("invite", {})
        admin_room_id = _find_admin_room_in_room_data(joined_rooms | invited_rooms)

        if admin_room_id:
            break
        else:
            await asyncio.sleep(3)
            count = count + 1

    assert admin_room_id is not None, f"Hookshot did not send admin room invite : {json.dumps(sync_response)}"

    # Accept the invite to the admin room
    await aiohttp_post_json(
        f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{admin_room_id}/join",
        {},
        {"Authorization": f"Bearer {user_access_token}"},
        ssl_context,
    )

    # Wait for and extract webhook URL from hookshot's response in the admin room
    webhook_url = None
    count = 0
    while count < 10:
        messages = await aiohttp_get_json(
            f"https://synapse.{generated_data.server_name}/_matrix/client/v3/rooms/{admin_room_id}/messages?dir=b&limit=10",
            {"Authorization": f"Bearer {user_access_token}"},
            ssl_context,
        )

        # Look for hookshot's response containing the webhook URL
        for event in messages.get("chunk", []):
            if (
                event.get("sender") == hookshot_mxid
                and "body" in event.get("content", {})
                and event["origin_server_ts"] > webhook_create_ts
            ):
                body = event["content"]["body"]
                if "http" in body:
                    # The webhook URL is the last line of the message
                    webhook_url = body.split("\n")[-1].strip()
                    assert urlparse(webhook_url).hostname == f"synapse.{generated_data.server_name}", (
                        f"Unexpected webhook URL found in admin room : {body}"
                    )
                    assert urlparse(webhook_url).scheme == "https", (
                        f"Unexpected webhook scheme found in admin room : {body}"
                    )
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

    answer = await aiohttp_post_json(
        webhook_url,
        test_payload,
        {},
        ssl_context,
    )
    assert answer["ok"]

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
                if "Test webhook payload" in body:
                    payload_found = True
                    break

        if payload_found:
            break
        else:
            await asyncio.sleep(3)
            count = count + 1

    assert payload_found, (
        f"Hookshot answered {answer} but did not post webhook {webhook_id} payload to room : {json.dumps(messages)}"
    )

    return room_id


# This creates an unencrypted room, invites hookshot, creates a webhook,
# and verifies that hookshot posts webhook payloads to the room
@pytest.mark.skipif(not value_file_has("hookshot.enabled", True), reason="Hookshot not enabled")
@pytest.mark.skipif(
    semver.Version.is_valid(os.environ.get("MATRIX_TEST_FROM_REF", ""))
    and semver.VersionInfo.parse(os.environ.get("MATRIX_TEST_FROM_REF", "")).compare("26.1.3") <= 0
    and os.environ.get("PYTEST_CI_FIRST_STEP", "") == "1",
    reason="26.1.3 or earlier doesn't correctly mount widgets on the Synapse Ingress, so it fails before upgrading.",
)
@pytest.mark.asyncio_cooperative
async def test_hookshot_widget(
    kube_client: AsyncClient,
    ingress_ready,
    generated_data: ESSData,
    ssl_context,
):
    await ingress_ready("synapse")

    async with (
        aiohttp_client(ssl_context) as client,
        client.get(
            "https://127.0.0.1/_matrix/hookshot/widgetapi/v1/static",
            headers={"Host": f"synapse.{generated_data.server_name}"},
            server_hostname=f"synapse.{generated_data.server_name}",
        ) as response,
    ):
        assert response.status != 404
