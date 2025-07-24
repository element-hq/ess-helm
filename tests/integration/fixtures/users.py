# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field

import pytest

from ..lib.matrix_authentication_service import (
    create_mas_user,
    get_client_token,
)
from ..lib.synapse import create_synapse_user
from ..lib.utils import value_file_has
from .data import ESSData


@dataclass
class User:
    name: str
    admin: bool = field(default=False)
    access_token: str | None = field(default=None)


@pytest.fixture
async def users(
    request, pytestconfig, matrix_stack, secrets_generated, generated_data: ESSData, ssl_context, ingress_ready
):
    await ingress_ready("synapse")
    if value_file_has("matrixAuthenticationService.enabled", True):
        await ingress_ready("matrix-authentication-service")

    users = request.param
    assert isinstance(users, Iterable)

    wait_for_users = []
    if value_file_has("matrixAuthenticationService.enabled", True):
        admin_token = await get_client_token(f"mas.{generated_data.server_name}", generated_data, ssl_context)
        for user in users:
            wait_for_users.append(
                create_mas_user(
                    f"mas.{generated_data.server_name}",
                    user.name,
                    generated_data.secrets_random,
                    user.admin,
                    admin_token,
                    ssl_context,
                    pytestconfig,
                )
            )
    else:
        synapse_registration_shared_secret = await secrets_generated("SYNAPSE_REGISTRATION_SHARED_SECRET")
        for user in request.param:
            wait_for_users.append(
                create_synapse_user(
                    f"synapse.{generated_data.server_name}",
                    user.name,
                    generated_data.secrets_random,
                    user.admin,
                    synapse_registration_shared_secret,
                    ssl_context,
                    pytestconfig,
                )
            )
    tokens = await asyncio.gather(*wait_for_users)
    for i, user in enumerate(users):
        user.access_token = tokens[i]
    return users
