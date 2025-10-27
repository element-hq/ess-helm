#!/usr/bin/env bash

# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only
  
set -xe


matrixDirectory="$1"
targetDirectory="$2"

if [ ! -d "$matrixDirectory" ]; then
  echo "Please provide a valid path for the matrix directory"
  exit 1
fi

if [ ! -d "$targetDirectory" ]; then
  mkdir -p "$targetDirectory"
fi

touch "$targetDirectory/hostnames.yaml"
touch "$targetDirectory/secrets.yaml
"
varsfile="$matrixDirectory/vars.yml"
homeserverconfig="$matrixDirectory/synapse/config/homeserver.yaml"
servername=$(yq .matrix_domain "$varsfile")
synapseHost=$(yq "(.public_baseurl | match \"https://(.+)/\").captures[0].string" "$homeserverconfig")

yq -i ".serverName |= \"$servername\"" "$targetDirectory/hostnames.yaml"
yq -i ".synapse.ingress.host |= \"$synapseHost\"" "$targetDirectory/hostnames.yaml"
yq -i ".elementWeb.enabled |= (load(\"$varsfile\").matrix_client_element_enabled // true)" "$targetDirectory/hostnames.yaml"
yq -i ".elementWeb.ingress.host |= (load(\"$varsfile\").matrix_client_element_hostname // \"element.$servername\")" "$targetDirectory/hostnames.yaml"
yq -i ".matrixAuthenticationService.enabled |= (load(\"$varsfile\").matrix_authentication_service_enabled // false)" "$targetDirectory/hostnames.yaml"
yq -i ".matrixAuthenticationService.ingress.host |= (load(\"$varsfile\").matrix_authentication_service_hostname // \"CHANGEME\")" "$targetDirectory/hostnames.yaml"
yq -i ".synapse.macaroon.value |= (load(\"$varsfile\").matrix_synapse_macaroon_secret_key)" "$targetDirectory/secrets.yaml"
yq -i ".synapse.signingKey.value |= load_str(\"$matrixDirectory/synapse/config/$synapseHost.signing.key\")" "$targetDirectory/secrets.yaml"
yq -i ".synapse.registrationSharedSecret.value |= (load(\"$homeserverconfig\").registration_shared_secret)" "$targetDirectory/secrets.yaml"
