#!/usr/bin/env bash

# Copyright 2024-2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail

[ "$#" -ne 1 ] && echo "Usage: set_chart_version.sh <chart version>" && exit 1

version="$1"
scripts_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
chart_root=$( cd "$scripts_dir/../charts" &> /dev/null && pwd )

function set_chart_version() {
  chart_dir="$1"

  [ ! -d "$chart_dir" ] && echo "$chart_dir must be a directory that exists" && exit 1
  [ ! -f "$chart_dir/Chart.yaml" ] && echo "Chart.yaml not found in $chart_dir" && exit 1

  echo "Setting version to $version for $chart_dir"
  yq -i '(.dependencies[] | select(.repository | test("file://"))).version="'"$version"'"' "$chart_dir/Chart.yaml"
  yq -i '.version="'"$version"'"' "$chart_dir/Chart.yaml"
  yq -iP '.' "$chart_dir/Chart.yaml"
  # REUSE-IgnoreStart
  reuse annotate --copyright="Copyright 2024-$(date +%Y) New Vector Ltd" --license "AGPL-3.0-only" "$chart_dir/Chart.yaml"
  # REUSE-IgnoreEnd
}

[ ! -d "$chart_root" ] && echo "$chart_root must be a directory that exists" && exit 1

set_chart_version "$chart_root"/matrix-stack
