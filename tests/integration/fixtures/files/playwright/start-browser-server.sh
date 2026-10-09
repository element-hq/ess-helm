#!/bin/sh

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Start the browser server. The integration tests (fixtures/playwright.py) drive it over a
# websocket.

set -e

# Install the test CA certificate in the browser. The tests pass it in the
# ESS_HELM_BROWSER_CA_PEM environment variable, as a base64 encoded PEM: the docker daemon
# can run on another machine, which cannot see the filesystem
# of the machine that runs the tests, so a mounted file can be empty or missing here.
# Chromium has no option to receive a CA certificate on the command line. And on Linux it does
# not use the certificates of the system: it only uses the certificates of its own database,
# in ~/.pki/nssdb.
# The CA is installed before the browser server starts. A browser that is already running
# may ignore new certificates.
ca_file=/tmp/ess-helm-test-ca.pem
printf '%s' "$ESS_HELM_BROWSER_CA_PEM" | base64 -d > "$ca_file"
mkdir -p "$HOME/.pki/nssdb"
# certutil -N creates a new database. It fails when the database already exists. That is fine.
certutil -N --empty-password -d "sql:$HOME/.pki/nssdb" || true
certutil -A -t "C,," -n ess-helm-test-ca -d "sql:$HOME/.pki/nssdb" -i "$ca_file"

# Start the browser server with the launch config the tests pass in the
# ESS_HELM_BROWSER_LAUNCH_CONFIG environment variable, for the same reason as the CA above.
# The config makes the server listen on all interfaces, so the tests can reach the websocket
# from outside the container. And it maps the *.localhost names of the tests to the IP of
# the ingress on the docker network of the cluster (see fixtures/playwright.py for why the
# mapping is not in /etc/hosts).
launch_config=/tmp/ess-helm-browser-launch-config.json
printf '%s' "$ESS_HELM_BROWSER_LAUNCH_CONFIG" | base64 -d > "$launch_config"
exec playwright launch-server --browser chromium --config "$launch_config"
