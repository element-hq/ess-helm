#!/usr/bin/env bash

# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

set -xe


targetDirectory="$1"
homeserverconfig="$2"


if [ -z "$targetDirectory" ]; then
  echo "Please provide a valid path for the ESS-Helm values directory"
  echo "Usage: $0 <target_directory> <homeserver.yaml>"
  echo "Example: $0 ~/ess-helm-values /matrx/synapse/config/homeserver.yaml"
  exit 1
fi

if [ -z "$homeserverconfig" ]; then
  if [ -f "homeserver.yaml" ]; then
    homeserverconfig="homeserver.yaml"
  else
    echo "Please provide a valid path for the homeserver.yaml file"
    echo "try find / -name homeserver.yaml or copy the yaml file to the current directory"
    echo "and run the script again"
    echo "Usage: $0 <target_directory> <homeserver.yaml>"
    echo "Example: $0 ~/ess-helm-values /matrx/synapse/config/homeserver.yaml"
    exit 1
  fi
fi

read -p "Is your synapse running in a docker container? (y/n): " isDocker
if [[ "$isDocker" == "y" ]]; then
  # Get the list of running containers
  containers=$(docker ps --format '{{.Names}}')
  echo "Select the Synapse container from the list:"
  select synapseContainer in $containers; do
    if [[ -n "$synapseContainer" ]]; then
      echo "You selected: $synapseContainer"
      break
    else
      echo "Invalid selection. Please try again."
    fi
  done
fi


if [ ! -d "$targetDirectory" ]; then
  mkdir -p "$targetDirectory"
fi

touch "$targetDirectory/hostnames.yaml"
touch "$targetDirectory/secrets.yaml"

servername=$(yq '.servername' "$homeserverconfig")
synapseHost=$(yq '(.public_baseurl | match "https://(.+)/").captures[0].string' "$homeserverconfig")
macaroon=$(yq '.macaroon_secret_key' "$homeserverconfig")
registrationSharedSecret=$(yq '.registration_shared_secret' "$homeserverconfig")

# Check if the Synapse container is running
if [[ "$isDocker" == "y" ]]; then
  if ! docker ps --format '{{.Names}}' | grep -q "$synapseContainer"; then
    echo "Error: Synapse container '$synapseContainer' is not running."
    exit 1
  fi
fi

if [ "$isDocker" == "y" ]; then
  # Get the path to the signing key from the Docker container
  # Ensure $homeserverconfig contains the correct path accessible from *outside* the container
  signingKey=$(docker exec "$synapseContainer" cat "$(yq '.signing_key_path' "$homeserverconfig")")
else
  # Get the path to the signing key from the local file system
  signingKey=$(cat "$(yq '.signing_key_path' "$homeserverconfig")")
fi

if [ -z "$signingKey" ]; then
  echo "Error: signing key not found."
  exit 1
fi
if [ -z "$macaroon" ]; then
  echo "Error: macaroon not found."
  exit 1
fi
if [ -z "$servername" ]; then
  echo "Error: servername not found."
  exit 1
fi

yq -i ".serverName |= \"$servername\"" "$targetDirectory/hostnames.yaml"
yq -i ".synapse.ingress.host |= \"$synapseHost\"" "$targetDirectory/hostnames.yaml"
yq -i ".synapse.macaroon.value |= \"$macaroon\"" "$targetDirectory/secrets.yaml"
yq -i ".synapse.signingKey.value |= \"$signingKey\"" "$targetDirectory/secrets.yaml"
yq -i ".synapse.registrationSharedSecret.value |= \"$registrationSharedSecret\"" "$targetDirectory/secrets.yaml"

echo "Verify that the values are correct:"
echo "Servername (should be the ending of your mxids @user:servername)"
echo "for example for the mxid @alice:matrix.org the servername is matrix.org)"
echo "Servername: $servername"
echo "Synapse Host: $synapseHost"
echo "Signing Key: $signingKey"
echo "Macaroon: $macaroon"
echo "Registration Shared Secret: $registrationSharedSecret"
echo "Synapse container: $synapseContainer"
echo "Synapse container is running: $isDocker"
echo "Synapse container name: $synapseContainer"