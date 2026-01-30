#!/usr/bin/env bash

# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -e

k3d_cluster_name="ess-helm"
k3d_context_name="k3d-$k3d_cluster_name"
# Space separated list of namespaces to use
ess_namespaces=${ESS_NAMESPACES:-ess}

root_folder="$(git rev-parse --show-toplevel)"
ca_folder="$root_folder/.ca"
mkdir -p "$ca_folder"

PYTEST_KEEP_CLUSTER=1 pytest tests/integration --env-setup

k3d kubeconfig merge ess-helm -ds

for namespace in $ess_namespaces; do
  echo "Constructing ESS dependencies in $namespace"
  server_version=$(kubectl --context $k3d_context_name version | grep Server | sed 's/.*v/v/' | awk -F. '{print $1"."$2}')
  # We don't turn on enforce here as people may be experimenting but we do turn on warn so people see the warnings when helm install/upgrade
  cat <<EOF | kubectl --context $k3d_context_name apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: ${namespace}
  labels:
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: ${server_version}
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: ${server_version}
EOF
done
