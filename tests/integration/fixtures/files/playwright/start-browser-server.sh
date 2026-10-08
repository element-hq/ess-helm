#!/bin/sh

# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

# Start the browser server. The integration tests (fixtures/playwright.py) drive it over a
# websocket.

set -e

# Install the test CA certificate in the browser. The tests mount it at /ess-helm-test-ca.pem.
# Chromium has no option to receive a CA certificate on the command line. And on Linux it does
# not use the certificates of the system: it only uses the certificates of its own database,
# in ~/.pki/nssdb.
# The CA is installed before the browser server starts. A browser that is already running
# may ignore new certificates.
mkdir -p "$HOME/.pki/nssdb"
# certutil -N creates a new database. It fails when the database already exists. That is fine.
certutil -N --empty-password -d "sql:$HOME/.pki/nssdb" || true
certutil -A -t "C,," -n ess-helm-test-ca -d "sql:$HOME/.pki/nssdb" -i /ess-helm-test-ca.pem

# Start the browser server with the launch config the tests mount at
# /ess-helm-browser-launch-config.json. The config makes the server listen on all
# interfaces, so the tests can reach the websocket from outside the container. And it maps
# the *.localhost names of the tests to the IP of the ingress on the docker network of
# the cluster (see fixtures/playwright.py for why the mapping is not in /etc/hosts).
exec playwright launch-server --browser chromium --config /ess-helm-browser-launch-config.json
