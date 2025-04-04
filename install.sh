#!/bin/bash

# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# This script installs the Element Server Suite (ESS) Community Edition.
# It depends on the following tools:
# - kubectl: Command-line tool for interacting with Kubernetes clusters.
# - curl: Command-line tool for transferring data with URLs.
# - dig: DNS lookup utility for querying DNS records.
# - helm: Package manager for Kubernetes, used to deploy applications.

ESS_NAMESPACE="ess"
CONFIG_VALUES_PATH="$HOME/ess-config-values"
CERT_TYPES=("LETS_ENCRYPT" "WILDCARD_CERT_FILE" "INDIVIDUAL_CERTS" "EXISTING_REVERSE_PROXY")
CHECKMARK="✅️"
CROSS="❌"
TOTAL_STEPS=9

# Function to log the current step
# Arguments:
#   1. Step number
#   2. Step name
log_step() {
  STEP_NUMBER=$1
  STEP_NAME=$2
  echo -e "\nStep ${STEP_NUMBER}/${TOTAL_STEPS} - ${STEP_NAME}"
}

# Function to check DNS records
# Arguments:
#   1. Domain to check
#   2. List of domains for the installation
check_dns() {
  ip=$(dig +short "${1}" | tail -1)

  if [ -n "$ip" ]; then
    echo "$CHECKMARK $1 => $ip"
  else
    echo "$CROSS $1"
    echo "Please create / check DNS for the following domains: ${2}"
    exit 1
  fi
}

echo "Installing ESS Community Edition..."

# Step 1 - DNS
log_step 1 "DNS"

INSTALLATION_DOMAIN=""

until echo "$INSTALLATION_DOMAIN" | grep -P '(?=^.{5,254}$)(^(?:(?!\d+\.)[a-zA-Z0-9_\-]{1,63}\.?)+(?:[a-zA-Z]{2,})$)'; do
  read -r -p "What domain should be used for the installation?: " INSTALLATION_DOMAIN
done

DOMAINS=("$INSTALLATION_DOMAIN" "matrix.$INSTALLATION_DOMAIN" "chat.$INSTALLATION_DOMAIN" "account.$INSTALLATION_DOMAIN")
CHAT_DOMAIN="chat.$INSTALLATION_DOMAIN"

echo "Checking DNS records"
for domain in "${DOMAINS[@]}"; do
  check_dns "$domain" "${DOMAINS[*]}"
done

# Step 2 - Install k3s
log_step 2 "Install k3s"

read -r -p "Install k3s? [yN]: " INSTALL_K3S
if [ "${INSTALL_K3S,,}" == "y" ]; then
  curl -sfL https://get.k3s.io | sh -
  mkdir ~/.kube
  export KUBECONFIG=~/.kube/config
  # shellcheck disable=SC2024
  sudo k3s kubectl config view --raw >"$KUBECONFIG"
  chmod 600 "$KUBECONFIG"
  if grep "KUBECONFIG=~/.kube/config" ~/.bashrc; then
    echo "Kubeconfig exists in .bashrc, not updating"
  else
    echo "Adding kubeconfig to .bashrc"
    echo "KUBECONFIG=~/.kube/config" >>~/.bashrc
  fi
fi

# Step 3 - Install Helm
log_step 3 "Install Helm"
read -r -p "Install Helm? [yN]: " INSTALL_HELM
if [ "${INSTALL_HELM,,}" == "y" ]; then
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

if kubectl get namespace "$ESS_NAMESPACE" >/dev/null 2>&1; then
  echo "Namespace '$ESS_NAMESPACE' already exists, skippig creation"
else
  echo "Creating  kubernetes namespace 'ess'"
  kubectl create namespace ess
fi

# Step 4 - Create config values
log_step 4 "Create config. values"

CREATE_CONFIG_VALUES=1
if [ -d "$CONFIG_VALUES_PATH" ]; then
  read -r -p "Existing config values detected. Delete and start over? [nY]: " RECREATE_CONFIG_VALUES
  if [ "${RECREATE_CONFIG_VALUES,,}" != "y" ]; then
    CREATE_CONFIG_VALUES=0
  fi
fi

if [ "$CREATE_CONFIG_VALUES" -eq 1 ]; then
  mkdir "$CONFIG_VALUES_PATH"
else
  echo "Skipping config value creation"
fi

# Step 5 - SSL Certs
log_step 5 "SSL Certs."

echo "Next please select your SSL cert installation type"
echo "(Please note that currently only wildcard SSL certificate files are supported by this installation script.)"
select opt in "${CERT_TYPES[@]}"; do
  case $opt in
  "LETS_ENCRYPT")
    echo "Let's encrypt certs ... not implemented in the installer. Please continue with manual installation."
    exit 3
    ;;
  "WILDCARD_CERT_FILE")
    echo "Wildcard SSL certificate for ${INSTALLATION_DOMAIN}"
    CERT_FILE=""
    until [ -f "$CERT_FILE" ]; do
      read -r -p "Wildcard cert path: " CERT_FILE
    done
    KEY_FILE=""
    until [ -f "$KEY_FILE" ]; do
      read -r -p "Wildcard key path: " KEY_FILE
    done

    if kubectl -n ess get secret ess-certificate; then
      echo "Existing ess-certificate, skipping creation"
    else
      kubectl create secret tls ess-certificate -n ess --cert="${CERT_FILE}" --key="${KEY_FILE}"
    fi

    cp "./charts/matrix-stack/ci/fragments/quick-setup-wildcard-cert.yaml" "$CONFIG_VALUES_PATH/tls.yaml"
    break
    ;;
  "INDIVIDUAL_CERTS")
    echo "Individual certs ... not implemented in the installer. Please continue with manual installation."
    exit 4
    ;;
  "EXISTING_REVERSE_PROXY")
    echo "Existing reverse proxy ... not implemented in the installer. Please continue with manual installation."
    exit 5
    ;;
  *)
    echo "Invalid option"
    exit 2
    ;;
  esac
done

# Step 6 - Setting up the stack
log_step 6 "Setting up the stack"

cp "./charts/matrix-stack/ci/fragments/quick-setup-hostnames.yaml" "${CONFIG_VALUES_PATH}/hostnames.yaml"

sed -i "s/host: chat.your.tld/host: chat.${INSTALLATION_DOMAIN}/" "${CONFIG_VALUES_PATH}/hostnames.yaml"
sed -i "s/host: account.your.tld/host: account.${INSTALLATION_DOMAIN}/" "${CONFIG_VALUES_PATH}/hostnames.yaml"
sed -i "s/host: matrix.your.tld/host: matrix.${INSTALLATION_DOMAIN}/" "${CONFIG_VALUES_PATH}/hostnames.yaml"
sed -i "s/serverName: your.tld/serverName: ${INSTALLATION_DOMAIN}/" "${CONFIG_VALUES_PATH}/hostnames.yaml"

# Step 7 - Install the stack
log_step 7 "Installing the deployments"
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml -f ~/ess-config-values/tls.yaml --wait

# Step 8 - Register initial user
log_step 8 "Register initial user"
kubectl exec -n ess -it deploy/ess-matrix-authentication-service -- mas-cli manage register-user

# Step 9 - Check setup
log_step 9 "Check setup"
# Check that element web is accessible
if curl "https://${CHAT_DOMAIN}" >/dev/null 2>&1; then
  echo "${CHECKMARK} - Element web accessible at '${CHAT_DOMAIN}'"
else
  echo "${CROSS} - Element web not accessible at '${CHAT_DOMAIN}'. Please check and troubleshoot installation"
fi
