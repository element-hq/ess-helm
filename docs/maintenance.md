<!--
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Maintenance

**Contents**
- [Upgrading](#upgrading)
- [Backup & restore](#backup--restore)
  - [Backup](#backup)
  - [Restore](#restore)

## Upgrading

In order to upgrade your deployment, you should:
1. Read the release notes of the new version and check if there are any breaking changes. The file [CHANGELOG.md](../CHANGELOG.md) should be your first stop.
3. Adjust your values if necessary.
2. Re-run the install command. It will upgrade your installation to the latest version of the chart.

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
