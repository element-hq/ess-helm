#!/usr/bin/env bash

# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail

workdir="$PWD"
checkov_values="$1"
matrix_stack_path="$workdir/charts/matrix-stack"
echo "Testing matrix-stack with $checkov_values";
tmpdir=$(mktemp -d)
cd "$tmpdir"
helm template checkov -n ess -f "$workdir/$checkov_values" "$matrix_stack_path" | sed 's/{{//' | yq -s '.kind + "-" + .metadata.name'
# CKV_SECRET_6=Checksum contains fake data with low entropy
checkov -d . --skip-check CKV_SECRET_6  --quiet
cd -
