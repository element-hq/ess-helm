<!--
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Upgrading from Legacy Auth to Matrix Authentication Service with syn2mas

## Overview

The migration from Synapse's legacy authentication to Matrix Authentication Service (MAS) is a multi-step process that must be executed carefully. The `syn2mas` feature in the Helm chart provides a controlled way to perform this migration.

The deployment-markers mechanism will refuse to setup Matrix Authentication Service if your stack was setup with Synapse only. You first have to go through the syn2mas procedure.

The syn2mas migration will run in a couple of minutes. It involves **three key steps**, and the correct configuration of the Helm values is essential to ensure a smooth and safe upgrade.

| Step | Action | Result |
|------|--------|--------|
| 1 | Setup Matrix Authentication Service and enable `syn2mas` in dryRun mode | System remains in `legacy_auth`. Matrix Authentication Service is deployed in `read-only` mode. It initializes the database. Users are still able to login using the legacy authentication. |
| 2 | Run migration (dry run disabled) | System transitions to `syn2mas_migrated`. Users now login using the delegated authentication. Rollback to legacy authentication is not possible anymore. |
| 3 | Disable syn2mas | System finalizes to `delegated_auth`. syn2mas cannot be run anymore. |

## Step-by-Step Upgrade Process

### Step 1: Setup Matrix Authenticatin Service and prepare the migration

1. You need to enable Matrix Authentication Service. The minimal settings required are described in `charts/matrix-stack/ci/fragments/matrix-authentication-service-minimal.yaml`. This is a minimal configuration that you can use if :
   - The `initSecrets` job is enabled (default)
   - You are using the chart-managed Postgres Server (we recommend using an external Postgres Server)

2. If you are using an external Postgres database, please refer to the quick-setup example in `charts/matrix-stack/ci/fragments/quick-setup-postgresql.yaml` to configure the Matrix Authentication Service database.

3. If you have disabled the `initSecrets` job, please refer to the example in `charts/matrix-stack/ci/fragments/matrix-authentication-service-secrets-in-helm.yaml` to configure the secrets manually.

4. Enable syn2mas in dryRun mode using the example values in `charts/matrix-stack/ci/fragments/matrix-authentication-service-syn2mas-dryrun.yaml`.

5. Run the helm upgrade command:

```bash
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait
```

6. This step will deploy the following resources :
   - Matrix Authentication Service is deployed in `read-only` mode. It initializes the database.
   - The `syn2mas` job runs in `dry-run` mode. It makes sure that the migration is ready to run.
   - Synapse is remains available, and users are still able to login using the legacy authentication.
   - The system will remain in the `legacy_auth` state until the migration is complete.

7. You can check that Matrix Authentication Service is reachable on the host you configured in `matrixAuthenticationService.ingress.host`


### Step 2: Execute the syn2mas Migration

1. Disable syn2mas dryRun mode by setting `matrixAuthenticationService.syn2mas.dryRun: false`. See the example values in `charts/matrix-stack/ci/fragments/matrix-authentication-service-syn2mas-migrate.yaml`.

2. Run the helm upgrade command:

```bash
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait
```

2. This step will deploy the following resources :
   - The migration job is executed as a pre-upgrade hook.
   - The job will downscale Synapse and its workers to 0 replicas while the migration runs.
   - At the end of the migration, Synapse will be scaled back up to its original number of replicas.
   - Matrix Authentication Service restarts and is ready to serve the delegated authentication
   - The `MATRIX_STACK_MSC3861` marker is updated to reflect the `syn2mas_migrated` state.

Your users are now able to login using the delegated authentication. It is not possible to rollback to `legacy_auth` anymore, nor to run the syn2mas migration again.


### Step 3: Disable syn2mas

While syn2mas is enabled, everytime you will run `helm upgrade`, it will downscale Synapse and its workers to 0 replicas.

1. Disable syn2mas by setting `matrixAuthenticationService.syn2mas.enabled: false`.

2. Run the helm upgrade command:

```bash
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait
```

3. This step will deploy the following resources :
   - No change happens on Synapse and Matrix Authentication Service workloads.
   - The `MATRIX_STACK_MSC3861` marker is updated to reflect the `delegated_auth` state. It is not possible to run `syn2mas` anymore, nor to rollback to `legacy_auth`.

## Marker Transitions

If the `deploymentMarkers` feature is enabled, the `MATRIX_STACK_MSC3861` marker transitions will occur during the migration process:

1. **Start** – `legacy_auth` (initial state)
2. **After Step 1** – `legacy_auth` (migration not yet executed)
3. **After Step 2** – `syn2mas_migrated` (migration completed)
4. **After Step 3** – `delegated_auth` (migration finalized)

> ⚠️ **Note:** The `MATRIX_STACK_MSC3861` marker will **prevent downgrading** from `syn2mas_migrated` or `delegated_auth` back to `legacy_auth`.


## Important Notes

- Please make sure to backup the synapse database before running the migration.
- The migration is a **one-way process**.Once the system is in the `delegated_auth` state, it cannot be rolled back to `legacy_auth`.
