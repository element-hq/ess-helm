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
| 2 | Run migration (dry run disabled) | System transitions to `syn2mas_migrated`. Users now login using the delegated authentication. Rollback to legacy authentication is not possible any more.  syn2mas cannot be run any more. |
| 3 | Disable syn2mas | System finalizes to `delegated_auth`. |

## Important Notes

- Please make sure to backup the synapse database before running the migration.
- The migration is a **one-way process**.Once the system is in the `delegated_auth` state, it cannot be rolled back to `legacy_auth`.

## Step-by-Step Upgrade Process

### Step 1: Setup Matrix Authentication Service and prepare the migration

1. You need to enable Matrix Authentication Service. The minimal settings required are described in `charts/matrix-stack/ci/fragments/matrix-authentication-service-minimal.yaml`. This is a minimal configuration that you can use if :
   - The `initSecrets` job is enabled (default)
   - You are using the chart-managed Postgres Server (we recommend using an external Postgres Server)

2. To migrate passwords from Synapse to Matrix Authentication Service, you need to enable Synapse passwords scheme into Matrix Authentication Service.
   - Please refer to the [Matrix Authentication Service Migration documentation](https://element-hq.github.io/matrix-authentication-service/setup/migration.html) to see any other additional setting you might need.
   - Configure them under `matrixAuthenticationService.additional` according to the [advanced documentation](./advanced.md#configuring-matrix-authentication-service)

3. If you are using an external Postgres database, please refer to the quick-setup example in `charts/matrix-stack/ci/fragments/quick-setup-postgresql.yaml` to configure the Matrix Authentication Service database.

4. If you have disabled the `initSecrets` job, please refer to the example in `charts/matrix-stack/ci/fragments/matrix-authentication-service-secrets-in-helm.yaml` to configure the secrets manually.

5. Run the helm upgrade command and enable syn2mas with `--set matrixAuthenticationService.syn2mas.enabled=true` :

```bash
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait --set matrixAuthenticationService.syn2mas.enabled=true
```

6. This step will deploy the following resources :
   - Matrix Authentication Service is deployed in `read-only` mode. It initializes the database.
   - The `syn2mas` job runs in `dry-run` mode. It makes sure that the migration is ready to run.
   - Synapse is remains available, and users are still able to login using the legacy authentication.
   - The system will remain in the `legacy_auth` state until the migration is complete.

7. You can check that Matrix Authentication Service is reachable on the host you configured in `matrixAuthenticationService.ingress.host`


### Step 2: Execute the syn2mas Migration

1. Run the helm upgrade command with `--reuse-values` and `--set matrixAuthenticationService.syn2mas.dryRun=false`

```bash
helm upgrade --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack --reuse-values --wait --set matrixAuthenticationService.syn2mas.dryRun=false
```

When an OAuth Provider was used with synapse already, the config check hook will throw an error "SSO cannot be enabled when OAuth delegation is enabled".
To proceed also add `--set synapse.checkConfigHook.enabled=false`. This will cause the synapse service to not start after the migration.

```bash
helm upgrade --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack --reuse-values --wait --set matrixAuthenticationService.syn2mas.dryRun=false --set synapse.checkConfigHook.enabled=false
```

2. This step will deploy the following resources :
   - The migration job is executed as a pre-upgrade hook.
   - The job will downscale Synapse and its workers to 0 replicas while the migration runs.
   - At the end of the migration, Synapse will be scaled back up to its original number of replicas.
   - Matrix Authentication Service restarts and is ready to serve the delegated authentication
   - The `MATRIX_STACK_MSC3861` marker is updated to reflect the `syn2mas_migrated` state.

Your users are now able to login using the delegated authentication. It is not possible to rollback to `legacy_auth` any more, nor to run the syn2mas migration again.


### Step 3: Disable syn2mas

When in `syn2mas_migrated` state, running `helm upgrade` will prevent any deployment until `syn2mas` is disabled and the state becomes `delegated_auth`.

2. Run the helm upgrade command without syn2mas arguments:

Remember to remove any `synapse.additional` configuration referencing an OAuth Provider.

```bash
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait
```

3. This step will deploy the following resources :
   - No change happens on Synapse and Matrix Authentication Service workloads.
   - The `MATRIX_STACK_MSC3861` marker is updated to reflect the `delegated_auth` state. It is not possible to run `syn2mas` any more, nor to rollback to `legacy_auth`.

## Marker Transitions

If the `deploymentMarkers` feature is enabled, the `MATRIX_STACK_MSC3861` marker transitions will occur during the migration process:

1. **Start** – `legacy_auth` (initial state)
2. **After Step 1** – `legacy_auth` (migration not yet executed)
3. **After Step 2** – `syn2mas_migrated` (migration completed)
4. **After Step 3** – `delegated_auth` (migration finalized)

> ⚠️ **Note:** The `MATRIX_STACK_MSC3861` marker will :
> - **Prevent running syn2mas migration again** after it has run successfully and is in `syn2mas_migrated` state
> - **Prevent downgrading** from `syn2mas_migrated`/`delegated_auth` back to `legacy_auth`
