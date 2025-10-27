#!/usr/bin/env bash

# Copyright 2024 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -e

kind_cluster_name="ess-helm"

if kind get clusters 2> /dev/null| grep "$kind_cluster_name"; then
  kind delete cluster --name $kind_cluster_name
else
  echo "Kind cluster ${kind_cluster_name} already destoryed"
fi

if docker ps -a | grep "${kind_cluster_name}-registry"; then
  docker stop "${kind_cluster_name}-registry" || true
  docker rm "${kind_cluster_name}-registry" || true
else
  echo "Kind cluster's local registry already destroyed"
fi
