#!/usr/bin/env bash

# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail
shopt -s nullglob

[ "$#" -gt 1 ] && echo "Usage: assemble_ci_values_files_from_fragments.sh <optional values file prefix to restrict to>" 1>&2 && exit 1

scripts_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
values_file_root=$( cd "$scripts_dir/../charts/matrix-stack/ci" &> /dev/null && pwd )
user_values_file_root=$( cd "$scripts_dir/../charts/matrix-stack/user_values" &> /dev/null && pwd )
extra_values_file_root=$( cd "$scripts_dir/../charts/matrix-stack/ci_extra" &> /dev/null && pwd )
values_file_prefix="${1:-*}"

[ ! -d "$values_file_root" ] && echo "$values_file_root must be a directory that exists" 1>&2 && exit 1
[ ! -d "$user_values_file_root" ] && echo "$user_values_file_root must be a directory that exists" 1>&2 && exit 1

for values_file in "$values_file_root"/$values_file_prefix-values.yaml "$user_values_file_root"/$values_file_prefix-values.yaml "$extra_values_file_root"/$values_file_prefix-values.yaml; do
  if [ "$values_file_prefix" != '*' ] &&  [ ! -e "$values_file" ]; then
    echo "$values_file_prefix-values.yaml doesn't exist in $(dirname "$values_file"). Skipping"
    continue
  fi
  if ! source_fragments=$(grep -E '#\s+source_fragments:' "$values_file" | sed 's/.*:\s*//'); then
    echo "$values_file doesn't have a source_fragments header comment. Skipping"
    continue
  fi
  has_new_vector_ltd_copyright=$(grep -E '#\s+Copyright [0-9-]+ New Vector Ltd' "$values_file" || echo -n "")
  source_fragments=$(echo "$source_fragments" | tr " " "\n" | sort | uniq | tr "\n" " " | sed 's/^\s*//' | sed 's/\s*$//')

  yq_command='.'
  for fragment_name in ${source_fragments}; do
    fragment_filename="$values_file_root/fragments/$fragment_name"
    [ ! -f "$fragment_filename" ] && echo "$fragment_filename must be a file that exists" 1>&2 && exit 1
    yq_command="($yq_command *= load(\"$fragment_filename\"))"
  done

  # Remove all the licensing headers that have accumulated
  yq_command+=" head_comment=\"\""
  # Pretty print but with double quotes
  yq_command+=" style=\"double\""
  # Sort keys for diff stability if we reorder the fragments
  yq_command+=" | sort_keys(..)"
  # Remove any fields with null values so we have a way of removing things
  yq_command+=" | del(... | select(. == null))"
  # We could remove enabled: true for all default enabled components by setting enabled: null in their minimal values file,
  yq_command+=" | del(.deploymentMarkers.enabled | select(.))"
  yq_command+=" | del(.matrixRTC.enabled | select(.))"
  yq_command+=" | del(.elementAdmin.enabled | select(.))"
  yq_command+=" | del(.elementWeb.enabled | select(.))"
  yq_command+=" | del(.initSecrets.enabled | select(.))"
  yq_command+=" | del(.postgres.enabled | select(.))"
  yq_command+=" | del(.matrixAuthenticationService.enabled | select(.))"
  yq_command+=" | del(.synapse.enabled | select(.))"
  yq_command+=" | del(.wellKnownDelegation.enabled | select(.))"
  yq_command+=' | del(.. | select(tag == "!!map" and length == 0))'
  yq_command+=" | select((. | [\"deploymentMarkers\", \"initSecrets\", \"postgres\", \"wellKnownDelegation\"] - keys) | length > 0) head_comment=([\"deploymentMarkers\", \"initSecrets\", \"postgres\", \"wellKnownDelegation\"] - keys | join(\", \"))  + \" don't have any required properties to be set and defaults to enabled\""

  echo "Generating $values_file from $source_fragments";
  cat << EOF > "$values_file"
# source_fragments: $source_fragments
# DO NOT EDIT DIRECTLY. Edit the fragment files to add / modify / remove values

EOF
  yq -P "$yq_command" "$values_file_root/nothing-enabled-values.yaml" >> "$values_file"

  # REUSE-IgnoreStart
  reuse annotate --copyright-prefix=string --year "2025-$(date +%Y)" --copyright="Element Creations Ltd" --license "AGPL-3.0-only" "$values_file"
  if [ -n "$has_new_vector_ltd_copyright" ]; then
  reuse annotate --copyright-prefix=string --year "2024-2025" --copyright="New Vector Ltd" --license "AGPL-3.0-only" "$values_file"
  fi
  # REUSE-IgnoreEnd
done
