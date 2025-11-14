#!/usr/bin/env bash

# Copyright 2024 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -e

k3d_cluster_name="ess-helm"

if k3d cluster list 2> /dev/null | grep "$k3d_cluster_name"; then
  k3d cluster delete $k3d_cluster_name
else
  echo "k3d cluster ${k3d_cluster_name} already destoryed"
fi
