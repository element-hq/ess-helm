#!/usr/bin/env bash

# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail

has_missing_arches=0
while read -r line; do
  echo "Checking $line"
  architectures=$(skopeo inspect --raw "docker://$line" | jq '[.manifests[]? | select(.platform.os=="linux") | .platform.architecture] | join(",")' -r)

  # Image is a single arch / no wrapper manifest and so we assume it is amd64
  if [[ "$architectures" == "" ]]; then
    architectures="amd64"
  fi

  for arch in amd64 arm64; do
    if [[ "$architectures" != *"$arch"* ]]; then
      echo "- $line doesn't have $arch, only '$architectures'"
      has_missing_arches=1
    fi
  done
done < <(yq '.. | select(has("repository")) | .registry + "/" + .repository + ":" + .tag' charts/matrix-stack/values.yaml)

if [ $has_missing_arches == 1 ]; then
  echo "One or more images didn't have all architectures. Failing"
  exit 1;
fi
