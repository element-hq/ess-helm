#!/usr/bin/env bash

# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail

# Parse arguments: first argument is optional file pattern, rest are passed to ct lint
file_pattern="*"
ct_args=()

# If first argument doesn't start with -, it's a file pattern
if [[ "$#" -gt 0 && "${1:0:1}" != "-" ]]; then
  file_pattern="$1"
  shift  # Remove file pattern from arguments
fi

# Remaining arguments are passed to ct lint
ct_args=("$@")

# Setup temporary directory for backing up non-matching CI values files
temp_dir=$(mktemp -d)
trapped_files=()

# Function to restore backed up files (called by trap)
# shellcheck disable=SC2329,SC2317
cleanup() {
  local file
  for file in "${trapped_files[@]}"; do
    if [ -f "$temp_dir/$(basename "$file")" ]; then
      mv "$temp_dir/$(basename "$file")" "$file"
    fi
  done
  rm -rf "$temp_dir"
}

# Trap EXIT to ensure cleanup happens
trap cleanup EXIT INT TERM

# Filter CI values files if a specific pattern is provided
if [ "$file_pattern" != "*" ]; then
  ci_values_dir="charts/matrix-stack/ci"
  if [ -d "$ci_values_dir" ]; then
    # First check if any files match the pattern
    matching_files=$(find "$ci_values_dir" -name "$file_pattern*-values.yaml" | wc -l)
    if [ "$matching_files" -eq 0 ]; then
      echo "No CI values files match pattern '$file_pattern', skipping lint"
      exit 0
    fi
    
    # Move non-matching values files to temp directory
    for values_file in "$ci_values_dir"/*-values.yaml; do
      if [ -f "$values_file" ]; then
        basename_file=$(basename "$values_file")
        if [[ "$basename_file" != "$file_pattern"*-values.yaml ]]; then
          mv "$values_file" "$temp_dir/"
          trapped_files+=("$values_file")
          echo "Temporarily moved $values_file for selective linting"
        fi
      fi
    done
  fi
fi

temp_output_file=$(mktemp)

error=1

find . -type f -name '*.tpl' -exec grep -nE '\{\{[^}]*\$[^a-zA-Z0-9_][^}]*\}\}' {} + && {
  echo 'Error: $ is used in a .tpl files, but helm passes the local context to the special variable $ in included templates.'; exit 1 
} || echo "OK."

find . '(' -type f -name '*.tpl' -o -name '*.yaml' ')' -exec grep -nE '\{\{[^}]*merge\s[^}]*\}\}' {} + && {
  echo 'Error: merge function is used in a .yaml or .tpl files, but helm does not merge boolean properly : https://github.com/helm/helm/issues/5238. Use mustMergeOverwrite instead.'; exit 1 
} || echo "OK."

# Call the ct lint command and stream the output to stdout
if ct lint "${ct_args[@]}" 2>&1 | tee "$temp_output_file"
then
  # Check if there are any "[INFO] Fail:" lines in the output
  (grep -q '\[INFO\] Fail:'  "$temp_output_file") || \
  (grep -q '\[INFO\] Missing required value:'  "$temp_output_file") ||\
  error=0
fi

if [ "$error" -eq 1 ]; then
  # If found, exit with status code 1
  echo "Errors were raised while running ct lint, exiting with error"
  echo "------------------"
  grep '\[INFO\] Fail:'  "$temp_output_file"
  grep '\[INFO\] Missing required value:'  "$temp_output_file"
fi

rm "$temp_output_file"
exit $error
