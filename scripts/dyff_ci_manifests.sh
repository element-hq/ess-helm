#!/usr/bin/env bash

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Compare the CI values files of two repositories through their rendered
# manifests, as written by render_ci_manifests.sh. Only the values files of
# the two charts are checked.
# usage: dyff_ci_manifests.sh MODE OLD_CHART_DIR OLD_MANIFESTS_DIR NEW_CHART_DIR NEW_MANIFESTS_DIR
# MODE "list": print the name of each values file whose rendered manifests
#   differ, one per line. Print nothing when they are all the same.
# MODE "comment": print the body of a comment describing the differences of
#   the rendered manifests, with a section per changed values file. The
#   newlines are written as the "\n" escape, the caller expands them. Print
#   nothing when they are all the same.
# Exit codes: 0 the comparison ran, 1 two rendered manifests could not be compared.

set -euo pipefail

if [ $# -ne 5 ]; then
  echo "usage: dyff_ci_manifests.sh MODE OLD_CHART_DIR OLD_MANIFESTS_DIR NEW_CHART_DIR NEW_MANIFESTS_DIR" >&2
  exit 1
fi

mode=$1
old_chart_dir=$2
old_manifests_dir=$3
new_chart_dir=$4
new_manifests_dir=$5

if [ "$mode" != "list" ] && [ "$mode" != "comment" ]; then
  echo "MODE must be 'list' or 'comment'" >&2
  exit 1
fi

scripts_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# The values files of both repositories, without duplicates.
values_names=()
shopt -s nullglob
for values in "$old_chart_dir"/ci*/*values.yaml "$new_chart_dir"/ci*/*values.yaml; do
  values_names+=("$(basename "$values" ".yaml")")
done
shopt -u nullglob

comment_body=""

while read -r values_name; do
  [ -n "$values_name" ] || continue
  old_dir="$old_manifests_dir/$values_name"
  new_dir="$new_manifests_dir/$values_name"
  echo "Checking $values_name" >&2

  values_file_suffix=""
  on_both_branches="true"
  if [ ! -d "$old_dir" ]; then
    echo "  $values_name is new" >&2
    values_file_suffix=" (added)"
    on_both_branches="false"
  elif [ ! -d "$new_dir" ]; then
    echo "  $values_name was removed" >&2
    values_file_suffix=" (removed)"
    on_both_branches="false"
  fi

  if [ "$mode" == "list" ] && [ "$on_both_branches" == "false" ]; then
    # The values file is new or removed, all its rendered manifests changed.
    echo "$values_name"
    continue
  fi

  has_dyff="false"
  comment_templates_body=""
  while read -r templates_file; do
    [ -n "$templates_file" ] || continue

    if [[ "$templates_file" == ".yaml" ]] \
        && [ ! -s "$old_dir/$templates_file" ] \
        && [ ! -s "$new_dir/$templates_file" ]; then
      # helm sometimes renders an empty document, which is written to an empty
      # .yaml file. It is not a manifest, there is nothing to compare.
      continue
    fi

    if [ ! -f "$old_dir/$templates_file" ] || [ ! -f "$new_dir/$templates_file" ]; then
      # A rendered manifest was added or removed.
      echo "  $templates_file was added or removed" >&2
      if [ "$mode" == "list" ]; then
        has_dyff="true"
        break
      fi
      if [ ! -f "$old_dir/$templates_file" ]; then
        kind=$(yq '.kind' "$new_dir/$templates_file")
        name=$(yq '.metadata.name' "$new_dir/$templates_file")
        namespace=$(yq '.metadata.namespace' "$new_dir/$templates_file")
        if [ "$on_both_branches" == "true" ]; then
          comment_templates_body+="@@ $kind/$namespace/$name @@\n"
          while IFS= read -r line; do
            comment_templates_body+="+ $line\n"
          done < "$new_dir/$templates_file"
          comment_templates_body+="\n\n"
        else
          comment_templates_body+="$kind/$namespace/$name added\n"
        fi
      else
        kind=$(yq '.kind' "$old_dir/$templates_file")
        name=$(yq '.metadata.name' "$old_dir/$templates_file")
        namespace=$(yq '.metadata.namespace' "$old_dir/$templates_file")
        if [ "$on_both_branches" == "true" ]; then
          comment_templates_body+="@@ $kind/$namespace/$name @@\n"
          while IFS= read -r line; do
            comment_templates_body+="- $line\n"
          done < "$old_dir/$templates_file"
          comment_templates_body+="\n\n"
        else
          comment_templates_body+="$kind/$namespace/$name removed\n"
        fi
      fi
      continue
    fi

    dyff_exit_code=0
    dyff_detail=$("$scripts_dir/dyff_manifests.sh" "$old_dir/$templates_file" "$new_dir/$templates_file") || dyff_exit_code=$?
    if [ "$dyff_exit_code" -eq 2 ]; then
      # The script has already printed why the files could not be compared
      exit 1
    fi
    if [ "$dyff_exit_code" -eq 1 ]; then
      echo "  $templates_file has a dyff" >&2
      if [ "$mode" == "list" ]; then
        has_dyff="true"
        break
      fi
      kind=$(yq '.kind' "$new_dir/$templates_file")
      name=$(yq '.metadata.name' "$new_dir/$templates_file")
      namespace=$(yq '.metadata.namespace' "$new_dir/$templates_file")
      comment_templates_body+=$(sed -e '/^!/d' -e "s|^@@\(.*\)@@|@@ $kind/$namespace/$name -\1@@|" <<< "$dyff_detail")
      comment_templates_body+="\n\n\n"
    fi
  done < <(
    # dotglob lists the .yaml files that helm empty documents are written to.
    shopt -s dotglob nullglob
    for file in "$old_dir"/*.yaml "$new_dir"/*.yaml; do
      basename "$file"
    done | sort -u
  )

  if [ "$mode" == "list" ]; then
    if [ "$has_dyff" == "true" ]; then
      echo "$values_name"
    fi
  elif [ -n "$comment_templates_body" ]; then
    comment_body+="<details><summary><b>$values_name.yaml$values_file_suffix</b></summary>\n"
    comment_body+='\n```diff\n'
    comment_body+="$comment_templates_body"
    comment_body+='```\n'
    comment_body+="\n</details>\n"
  fi
done < <(printf '%s\n' "${values_names[@]}" | sort -u)

if [ "$mode" == "comment" ] && [ -n "$comment_body" ]; then
  echo "$comment_body"
fi
