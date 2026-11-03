#!/usr/bin/env bash

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Compare two rendered manifest files with dyff.
# The labels that are deployment noise are excluded, see templates-dyff workflow.
# Exit codes: 0 the manifests are the same, 1 the manifests differ, 2 dyff could not compare.

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: dyff_manifests_dirs.sh OLD_MANIFEST NEW_MANIFEST" >&2
  exit 2
fi

old_manifest=$1
new_manifest=$2

# We exclude the hash labels and the version label. They only add noise:
# tests confirm they are set correctly.
excludes=(
  '--exclude-regexp' 'metadata.labels.k8s.element.io/.*-hash'
  '--exclude-regexp' 'spec.template.metadata.labels.k8s.element.io/.*-hash'
  '--exclude-regexp' 'metadata.labels.app.kubernetes.io/version'
  '--exclude-regexp' 'spec.template.metadata.labels.app.kubernetes.io/version'
)

# dyff exits 0 when the manifests are the same and 1 when they differ.
# Any other exit code means dyff could not compare them.
dyff_detail=""
dyff_exit_code=0
dyff_detail=$(dyff between --set-exit-code --omit-header --output=github "${excludes[@]}" \
  "$old_manifest" "$new_manifest" 2>&1) || dyff_exit_code=$?

if [ "$dyff_exit_code" -gt 1 ]; then
  echo "$dyff_detail" >&2
  echo "dyff could not compare $old_manifest and $new_manifest" >&2
  exit 2
fi

echo "$dyff_detail"
exit "$dyff_exit_code"
