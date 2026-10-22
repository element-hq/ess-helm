#!/usr/bin/env bash

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Render the manifests of all the CI values files of a chart, one directory
# per values file. The manifests of a values file are written to
# OUTPUT_DIR/<values file name>/.
# usage: render_ci_manifests.sh CHART_DIR OUTPUT_DIR

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: render_ci_manifests.sh CHART_DIR OUTPUT_DIR" >&2
  exit 1
fi

chart_dir=$1
output_dir=$2

render_values_file() {
  values=$1
  values_file=$(basename "$values" ".yaml")
  echo "Rendering the manifests of $values_file"
  mkdir -p "$output_dir/$values_file"
  (helm template \
      -n ess-ci \
      -a monitoring.coreos.com/v1/ServiceMonitor \
      -a cert-manager.io/v1/Certificate \
      -f "$values" "$chart_dir") | \
  yq ea '[.] | .[] | splitDoc' | \
  yq -s "\"$output_dir/$values_file/\" + ([.kind, .metadata.name] | join(\"-\") | downcase) + \".yaml\""
}
export -f render_values_file
export chart_dir output_dir

shopt -s nullglob
values_files=("$chart_dir"/ci*/*values.yaml)
shopt -u nullglob

if [ "${#values_files[@]}" -eq 0 ]; then
  echo "No values files found in $chart_dir/ci*" >&2
  exit 1
fi

# Rendering the manifests is the slow part of a dyff. We render the
# values files in parallel to use all the CPU cores of the machine.
# shellcheck disable=SC2016  # $1 is filled in by xargs
printf '%s\n' "${values_files[@]}" | \
  xargs -P "$(nproc)" -n1 bash -c 'set -euo pipefail; render_values_file "$1"' _
