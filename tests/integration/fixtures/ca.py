# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import ssl

import pytest

from ..artifacts import get_ca


@pytest.fixture(scope="session")
async def root_ca():
    return get_ca("ESS CA")


@pytest.fixture(scope="session")
async def delegated_ca(root_ca):
    return get_ca("ESS CA Delegated", root_ca)


@pytest.fixture(scope="session")
async def ssl_context(root_ca):
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=root_ca.cert_as_pem())
    return context
