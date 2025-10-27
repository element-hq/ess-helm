#!/usr/bin/env bash

# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

#
# A script which checks that an appropriate news file has been added on this
# branch.

echo -e "+++ \033[32mChecking newsfragment\033[m"

set -e

pr="$1"

# Print a link to the contributing guide if the user makes a mistake
CONTRIBUTING_GUIDE_TEXT="!! Please see the readme for help writing your changelog entry:
https://github.com/element-hq/ess-helm/blob/main/README.md#changelog"

# If towncrier returns a non-zero exit code, print the contributing guide link and exit
towncrier check  --compare-with="origin/main" || (echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2 && exit 1)

echo
echo "--------------------------"
echo

matched=0
for f in $(git diff --diff-filter=d --name-only origin/main... -- ':(exclude)newsfragments/.gitkeep'  newsfragments); do
    # check that any modified newsfiles on this branch have the appropriate punctuation on the first line.
    lastchar=$(head -n 1 "$f" | tr -d '\n' | tail -c 1)
    if [ "$lastchar" != '.' ] && [ "$lastchar" != '!' ]; then
        echo -e "\e[31mERROR: newsfragment $f does not end with a '.' or '!'\e[39m" >&2
        echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2
        exit 1
    fi
    [[ -n "$pr" && "$f" == newsfragments/"$pr".* ]] && matched=1
done

if [[ -n "$pr" && "$matched" -eq 0 ]]; then
    echo -e "\e[31mERROR: Did not find a news fragment with the right number: expected newsfragments/$pr.*.\e[39m" >&2
    echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2
    exit 1
fi
