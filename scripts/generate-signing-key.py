#!/usr/bin/env python3

# Copyright 2024 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import signedjson.key

signing_key = signedjson.key.generate_signing_key(0)
print(f"Signing key: {signing_key.alg} {signing_key.version} {signedjson.key.encode_signing_key_base64(signing_key)}")
print(
    f"Verify key: {signing_key.alg} {signing_key.version} \
{signedjson.key.encode_verify_key_base64(signing_key.verify_key)}"
)
