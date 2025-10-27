#!/usr/bin/env bash

# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -e

kind_cluster_name="ess-helm"
kind_context_name="kind-$kind_cluster_name"
# Space separated list of namespaces to use
ess_namespaces=${ESS_NAMESPACES:-ess}

root_folder="$(git rev-parse --show-toplevel)"
ca_folder="$root_folder/.ca"
mkdir -p "$ca_folder"

if docker ps -a | grep "${kind_cluster_name}-registry"; then
  docker stop "${kind_cluster_name}-registry" || true
  docker rm "${kind_cluster_name}-registry" || true
fi
if kind get clusters 2>/dev/null | grep "$kind_cluster_name"; then
  echo "Cluster '$kind_cluster_name' is already provisioned by Kind"
else
  echo "Creating new Kind cluster '$kind_cluster_name'"
  (cd "$root_folder/tests/integration/fixtures/files/clusters"; kind create cluster --name "$kind_cluster_name" --config "kind.yml")
fi

network=$(docker inspect $kind_cluster_name-control-plane | jq '.[0].NetworkSettings.Networks | keys | .[0]' -r)
docker run \
    -d --restart=always -p "127.0.0.1:5000:5000" --network "$network" --network-alias "registry" --name "${kind_cluster_name}-registry" \
    registry:2

helm --kube-context $kind_context_name upgrade -i ingress-nginx --repo https://kubernetes.github.io/ingress-nginx ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  -f "$root_folder/tests/integration/fixtures/files/charts/ingress-nginx.yml"

helm --kube-context $kind_context_name upgrade -i metrics-server --repo https://kubernetes-sigs.github.io/metrics-server metrics-server \
  --namespace kube-system \
  -f "$root_folder/tests/integration/fixtures/files/charts/metrics-server.yml"

helm --kube-context $kind_context_name upgrade -i prometheus-operator-crds --repo https://prometheus-community.github.io/helm-charts prometheus-operator-crds \
  --namespace prometheus-operator \
  --create-namespace

helm --kube-context $kind_context_name upgrade -i cert-manager --repo https://charts.jetstack.io cert-manager \
  --namespace cert-manager \
  --create-namespace \
  -f "$root_folder/tests/integration/fixtures/files/charts/cert-manager.yml"

# Create a new CA certificate
if [[ ! -f "$ca_folder"/ca.crt || ! -f "$ca_folder"/ca.pem ]]; then
  cat <<EOF | kubectl --context $kind_context_name apply -f -
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: ess-ca
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ess-ca
  namespace: cert-manager
spec:
  isCA: true
  commonName: ess-ca
  secretName: ess-ca
  # 10 years
  duration: 87660h0m0s
  privateKey:
    algorithm: RSA
  issuerRef:
    name: ess-ca
    kind: ClusterIssuer
    group: cert-manager.io
---
EOF
  kubectl --context $kind_context_name -n cert-manager wait --for condition=Ready Certificate/ess-ca
else
  kubectl --context $kind_context_name delete ClusterIssuer ess-ca 2>/dev/null || true
  kubectl --context $kind_context_name -n cert-manager delete Certificate ess-ca 2>/dev/null || true
  kubectl --context $kind_context_name -n cert-manager delete Secret ess-ca 2>/dev/null || true
  kubectl --context $kind_context_name -n cert-manager create secret generic ess-ca \
    --type=kubernetes.io/tls \
    --from-file=tls.crt="$ca_folder"/ca.crt \
    --from-file=tls.key="$ca_folder"/ca.pem \
    --from-file=ca.crt="$ca_folder"/ca.crt
fi

cat <<EOF | kubectl --context $kind_context_name apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: ess-selfsigned
spec:
  ca:
    secretName: ess-ca
EOF

if [[ ! -f "$ca_folder"/ca.crt || ! -f "$ca_folder"/ca.pem ]]; then
  kubectl --context $kind_context_name -n cert-manager get secret ess-ca -o jsonpath="{.data['ca\.crt']}" | base64 -d > "$ca_folder"/ca.crt
  kubectl --context $kind_context_name -n cert-manager get secret ess-ca -o jsonpath="{.data['tls\.key']}" | base64 -d > "$ca_folder"/ca.pem
fi

for namespace in $ess_namespaces; do
  echo "Constructing ESS dependencies in $namespace"
  server_version=$(kubectl --context $kind_context_name version | grep Server | sed 's/.*v/v/' | awk -F. '{print $1"."$2}')
  # We don't turn on enforce here as people may be experimenting but we do turn on warn so people see the warnings when helm install/upgrade
  cat <<EOF | kubectl --context $kind_context_name apply -f -
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
