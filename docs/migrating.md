<!--
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Migrating

## General migration plan

Element provides a migration tool that can be used to convert any existing Synapse (and optionally, MAS) configuration to Element Server Suite.

The steps are as follows:

1. If you are setting up ESS on a server without a Kubernetes cluster available, we recommend that you follow the [ESS installation instructions](https://github.com/element-hq/ess-helm/blob/main/README.md#kubernetes-single-node-setup-with-k3s) to setup a Kubernetes single-node K3S deployment.
2. Follow the [ess-migration-tool instructions](https://github.com/element-hq/ess-helm/blob/main/packages/ess-migration-tool/README.md) to migrate your Synapse and MAS configuration files to ESS Helm values and Kubernetes secrets.
3. Regarding TLS, you can let ESS manage TLS certificates for you, or you can serve TLS using your own reverse proxy. Follow the [Certificates setup instructions](https://github.com/element-hq/ess-helm/blob/main/README.md#certificates) according to your needs.
4. Setup ESS using the `helm` command. If you are using TLS managed by ESS, you will have to add `-f <path to configured tls.yaml>` to the helm command provided by the ESS migration tool.
5. The ESS Migration Tool will also suggest commands allowing you to migrate your Synapse media to ESS, as well as your existing Synapse database.
