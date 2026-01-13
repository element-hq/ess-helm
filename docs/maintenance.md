<!--
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Maintenance

**Contents**
- [Upgrading](#upgrading)
- [Backup & restore](#backup--restore)
  - [Backup](#backup)
  - [Restore](#restore)
- [Installation State](#installation-state)

## Upgrading

In order to upgrade your deployment, you should:
1. Read the release notes of the new version and check if there are any breaking changes. The file [CHANGELOG.md](../CHANGELOG.md) should be your first stop.
3. Adjust your values if necessary.
2. Re-run the [install](https://github.com/element-hq/ess-helm/tree/main?tab=readme-ov-file#installation) command. It will upgrade your installation to the latest version of the chart.

## Backup & restore

### Backup

You need to backup a couple of things to be able to restore your deployment:

1. Stop Synapse and Matrix Authentication Service workloads:
```sh
kubectl scale sts -l "app.kubernetes.io/component=matrix-server" -n ess --replicas=0
kubectl scale deploy -l "app.kubernetes.io/component=matrix-authentication" -n ess --replicas=0
```
2. The database. You need to backup your database and restore it on a new deployment.
  1. If you are using the provided Postgres database, build a dump using the command `kubectl exec --namespace ess -it sts/ess-postgres -- pg_dumpall -U postgres > dump.sql`. Adjust to your own kubernetes namespace and release name if required.
  2. If you are using your own Postgres database, please build your backup according to your database documentation.
3. Your values files used to deploy the chart
4. The chart will generate some credentials in a `Secret` if you do not provide them. To copy them to a local file, you can run the following command: `kubectl get secrets -l "app.kubernetes.io/managed-by=matrix-tools-init-secrets"  -n ess -o yaml > secrets.yaml`. Adjust to your own kubernetes namespace if required.
5. The chart will generate some flags/markers in a `ConfigMap` to ensure that `helm upgrade` with different values doesn't put the installation in an invalid state. To copy them to a local file, you can run the following command: `kubectl get configmap -l "app.kubernetes.io/managed-by=matrix-tools-deployment-markers"  -n ess -o yaml > configmaps.yaml`. Adjust to your own kubernetes namespace if required.
6. The media files: Synapse stores media in a persistent volume that should be backed up. On a default K3s setup, you can find where synapse media is stored on your node using the command `kubectl get pv -n ess -o yaml | grep synapse-media`.
7. Run the `helm upgrade --install....` command again to restore your workload's pods.

### Restore

1. Recreate the namespace and the backed-up secret in step 3: 
```sh
kubectl create ns ess
kubectl -n ess apply -f secrets.yaml
kubectl -n ess apply -f configmaps.yaml
```
2. Redeploy the chart using the values backed-up in step 2.
3. Stop Synapse and Matrix Authentication Service workloads:
```sh
kubectl scale sts -l "app.kubernetes.io/component=matrix-server" -n ess --replicas=0
kubectl scale deploy -l "app.kubernetes.io/component=matrix-authentication" -n ess --replicas=0
```
4. Restore the postgres dump. If you are using the provided Postgres database, this can be achieved using the following commands:
```sh
# Drop newly created databases and roles
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP DATABASE matrixauthenticationservice'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP DATABASE synapse'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP ROLE synapse_user'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP ROLE matrixauthenticationservice_user'
kubectl cp dump.sql ess-postgres-0:/tmp -n ess
kubectl exec -n ess sts/ess-postgres -- bash -c "psql -U postgres -d postgres < /tmp/dump.sql"
```
Adjust to your own kubernetes namespace and release name if required.

4. Restore the synapse media files using `kubectl cp` to copy them in Synapse pod. If you are using K3s, you can find where the new persistent volume has been mounted with `kubectl get pv -n ess -o yaml | grep synapse-media` and copy your files in the destination path.
5. Run the `helm upgrade --install....` command again to restore your workload's pods.


## Installation State

The below documents various stores of the state for the installation, that the chart controls.
These stores of state may have a different lifecycle to the chart itself, i.e. may persist beyond `helm uninstall`, and their lifecycle is documented below.

### Postgres

By default (`postgres.enabled: true`) the chart will deploy a Postgres instance in the cluster, if Synapse or Matrix Authentication Service are deployed.
This is to enable a quick, easy and self-contained way of deploying the stack, whilst minimising external dependencies

The chart will construct a `PersistentVolumeClaim` to persist the Postgres databases.
By default, this `PersistentVolumeClaim` will not be deleted on `helm uninstall`.
This is to prevent data loss.
This behaviour can be changed by setting `postgres.storage.resourcePolicy: delete` rather than `keep`.

Alternatively, an existing `PersistentVolumeClaim` that is not managed by the chart, can be used by specifying `postgres.storage.existingClaim`.

Finally, the recommended approach is to use a Postgres instance that is not managed by the chart.
This can be done by setting `postgres.enabled: false` and configuring Synapse and Matrix Authentication Service with details of these Postgres instance(s).

### Synapse Media

If Synapse is enabled, the chart will default to constructing a `PersistentVolumeClaim` to persist uploaded media.
By default, this `PersistentVolumeClaim` will not be deleted on `helm uninstall`.
This is to prevent data loss.
This behaviour can be changed by setting `synapse.media.storage.resourcePolicy: delete` rather than `keep`.

Alternatively, an existing `PersistentVolumeClaim`, that is not managed by the chart, can be used by specifying `synapse.media.storage.existingClaim`.

### Generated Secrets

By default (`initSecrets.enabled: true`) the chart will run a pre-install / pre-upgrade Helm hook to generate a variety of credentials that don't relate to external resources.
This is to enable a quick and easy initial installation, without having to manually generate credentials, in a way that will work with tools like ArgoCD that don't support Helm's `lookup` function.
The chart will create appropriate `Role` and `RoleBindings` in the installation namespace to facilitate this.

The generated `Secret` will have label `app.kubernetes.io/managed-by=matrix-tools-init-secrets`.
As it is generated & managed with pre-install / pre-upgrade Hooks and no post-uninstall Hook is configured, this `Secret` will not be removed on `helm uninstall`.
This is to prevent data loss, as some of the generated credentials (e.g. Synapse's signing key) have impact if they are changed without additional configuration.

Each credential can be manually specified either directly in the Helm values or by referencing an existing `Secret` and associated key.

The generated secrets functionality can be turned off by setting `initSecrets.enabled: false` and then the chart will require you to provide all required credentials as described above.

### Deployment Markers

By default (`deploymentMarkers.enabled: true`) the chart will run a pre-install / pre-upgrade / post-upgrade Helm hook to check and record the state of the installation in a `ConfigMap`.
This is to prevent components being enabled, disabled or otherwise put into some states that could cause data-corruption.
The chart will create appropriate `Role` and `RoleBindings` in the installation namespace to facilitate this.

The generated `ConfigMap` will have label `app.kubernetes.io/managed-by=matrix-tools-deployment-markers`.
As it is generated & managed with pre-install / pre-upgrade / post-upgrade Hooks and no post-uninstall Hook is configured, this `ConfigMap` will not be removed on `helm uninstall`.
This is to prevent invalid states being entered on reinstallation, given that the default chart behaviour is to keep the Postgres database between reinstallations.

The deployment markers functionality can be turned off by setting `deploymentMarkers.enabled: false` and the chart will not protect you from various invalid changes to the values.
