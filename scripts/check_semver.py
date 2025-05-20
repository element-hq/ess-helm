#!/usr/bin/env python3

# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import sys

import semver

version = sys.argv[1]
if semver.Version.is_valid(version):
    exit(0)
else:
    print(f"Version {version} is not semver")
    exit(1)
