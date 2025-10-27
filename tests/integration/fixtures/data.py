# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import secrets
import string
from dataclasses import dataclass

import pytest

from ..artifacts import CertKey


def unsafe_token(size):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for i in range(size))


def random_string(choice, size):
    return "".join([random.choice(choice) for _ in range(0, size)])


@dataclass(frozen=True)
class ESSData:
    secrets_random: str
    # Just for persisting across sessions, shouldn't be directly accessed
    _root_ca: CertKey

    # Only here because we need to refer to it, in the tests, after the Secret has been constructed
    mas_oidc_client_secret: str

    @property
    def release_name(self):
        return f"pytest-{self.secrets_random}"

    @property
    def ess_namespace(self):
        return f"ess-{self.secrets_random}"

    @property
    def server_name(self):
        return f"ess-test-{self.secrets_random}.localhost"

    @classmethod
    def from_dict(cls, kv):
        return ESSData(
            secrets_random=kv["secrets_random"],
            mas_oidc_client_secret=kv["mas_oidc_client_secret"],
            _root_ca=CertKey.from_dict(kv["ca"]),
        )

    def to_json_mapping(self) -> dict:
        return {
            "secrets_random": self.secrets_random,
            "ca": self._root_ca.to_json_mapping(),
            "mas_oidc_client_secret": self.mas_oidc_client_secret,
        }


@pytest.fixture(scope="session")
async def generated_data(pytestconfig, root_ca):
    serialized_data = pytestconfig.cache.get("ess-helm/generated-data", None)
    if serialized_data:
        data = ESSData.from_dict(serialized_data)
    else:
        data = ESSData(
            secrets_random=random_string(string.ascii_lowercase + string.digits, 8),
            _root_ca=root_ca,
            mas_oidc_client_secret=secrets.token_urlsafe(36),
        )
        pytestconfig.cache.set("ess-helm/generated-data", data.to_json_mapping())
    return data
