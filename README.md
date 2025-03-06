<!--
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
-->

<p align="center">
<img src="https://img.shields.io/github/check-runs/element-hq/ess-helm/main">
<img alt="GitHub License" src="https://img.shields.io/github/license/element-hq/ess-helm">
<img alt="GitHub Issues or Pull Requests" src="https://img.shields.io/github/v/release/element-hq/ess-helm">
<img alt="GitHub Issues or Pull Requests" src="https://img.shields.io/github/issues/element-hq/ess-helm">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/images/Element-Server-Suite-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/assets/images/Element-Server-Suite-light.png">
  <img alt="ESS">
</picture>
<img>
</p>
<h1 align="center">The Element Matrix Server Suite for Community </h1>

<p align="center">
<b>Deploy Element Matrix Chat, with minimal configuration but maximal configurability.</b>
</p>

## Overview

Element Server Suite Community Edition allows you to deploy an official Element Matrix Stack using the same helm-charts we use for our own production deployments. It allows you to very quickly configure a matrix stack supporting all the latest Matrix Features:

- Element X
- Next Gen Matrix Authentication
- Synapse Workers to scale your deployment

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/images/ESS-Community-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/assets/images/ESS-Community-light.png">
  <img alt="ESS Community Diagram">
</picture>
</p>

ESS Community Edition configures the following components automatically. It is possible to enable/disable each on a per-component basis. They can also be customized using dedicated values:

- HAProxy: Provides the routing to Synapse processes.
- Synapse: Provides the Matrix homeserver, allowing you to communicate with the full Matrix network.
- Matrix Authentication Service: Handles the authentication of your users, compatible with Element X.
- Element Web: The official Matrix Web Client provided by Element.
- PostgreSQL: A packaged PostgreSQL server. It allows you to quickly set up the stack with Postgres provided. For a better long-term experience, please consider using your own PostgreSQL server installed with your system packages.

The documentation below assumes you are installing on a dedicated server. If you already have a reverse proxy configured (for instance if you share the machine with other services) see the [dedicated section](#set-up-element-server-suite-on-a-server--with-an-existing-reverse-proxy) to configure ESS behind this reverse proxy.

## Quick Start

**This readme is primarily aimed as a simple walkthrough to setup Element Server Suite - Community Edition.
Users experienced with Helm can refer directly to the chart README at [charts/matrix-stack/README.md](charts/matrix-stack/README.md)**.

## Resources requirements

The quick-setup relies on k3s. It requires at least 2 CPU cores and 2 GB of memory available.

## Prerequisites

You need to choose what your user's server name is going to be. The server name makes up the latter part of a user's Matrix ID. In the following example Matrix ID, `server-name.tld` is the server name, and should point to your Element Community Edition installation

  `@alice:server-name.tld`

**You will not be able to change your server name without resetting your database and losing the server.**

## Preparing the environment

### DNS

You need to create 4 DNS entries to set up Element Server Suite Community Edition. All of these DNS entries must point to your server.

- Server Name: This DNS entry should point to the installation ingress. It should be the `server-name.tld` you chose above.
- Synapse: For example `matrix.<server-name.tld>`
- Matrix Authentication Service: For example `account.<server-name.tld>`
- Element Web: This will be the address of the chat client of your server. For example `chat.<server-name.tld>`

### K3S \- Kubernetes Single Node

This guide suggests using K3S as the Kubernetes Node hosting ESS. Other options are possible, you can have your own Kubernetes cluster already, or use other clusters like [microk8s](https://microk8s.io/). Any Kubernetes distribution is compatible with Element Community Edition, so choose one according to your needs.

This will install K3S on the node, and configure its Traefik proxy automatically. If you want to configure K3S behind an existing reverse proxy on the same node, please see the [dedicated section](#set-up-element-server-suite-on-a-server--with-an-existing-reverse-proxy).

Run the following command to install K3S:

```
curl -sfL https://get.k3s.io | sh -
```

Once k3s is setup,  copy it’s kubeconfig to your home directory to get access to it:

```
mkdir ~/.kube
export KUBECONFIG=~/.kube/config
sudo k3s kubectl config view --raw > "$KUBECONFIG"
chmod 600 "$KUBECONFIG"
```

Install Helm, the Kubernetes Package Manager. You can use your [OS repository](https://helm.sh/docs/intro/install/) or call the following command:

```
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Create your Kubernetes Namespace where you will deploy the Element Server Suite Community Edition:

```
kubectl create namespace ess
```

Create a directory containing your Element Server Suite configuration values:

```
mkdir ~/ess-config-values
```

### TLS Certificates

We present here 3 options to set up certificates in Element Server Suite. To configure Element Server Suite behind an existing reverse proxy already serving TLS, you can skip this section.

#### Lets Encrypt

To use Let’s Encrypt with ESS Helm, you should use [Cert Manager](https://cert-manager.io/). This is a Kubernetes component which allows you to get certificates issued by an ACME provider. The installation follows the [official manual](https://cert-manager.io/docs/installation/helm/):

Add Helm Jetstack Repository:

```
helm repo add jetstack https://charts.jetstack.io --force-update
```

Install Cert-Manager:

```
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.17.0 \
  --set crds.enabled=true
```

Configure Cert-Manager to allow Element Server Suite Community Edition to request Let’s Encrypt certificates automatically. Create a “ClusterIssuer” resource in your k3s node to do so:

```
export USER_EMAIL=<your email>

kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: $USER_EMAIL
    privateKeySecretRef:
      name: letsencrypt-prod-private-key
    solvers:
      - http01:
          ingress:
            class: traefik
EOF
```

In your ess configuration values directory, copy the file `charts/matrix-stack/ci/fragments/quick-setup-letsencrypt.yaml` to `tls.yaml`.

#### Certificate File

##### Wildcard certificate

If your wildcard certificate covers both the server-name and the hosts of your services, you can use it directly.

Import your certificate file in your namespace using [kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_tls/):

```
kubectl create secret tls ess-certificate --cert=path/to/cert/file --key=path/to/key/file
```

In your ess configuration values directory, copy the file `charts/matrix-stack/ci/fragments/quick-setup-wildcard-cert.yaml` to `tls.yaml`. Adjust the TLS Secret name accordingly if needed.

##### Individual certificates

If you have a distinct certificate for each of your DNS names, you will need to import each certificate in your namespace using [kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_tls/):
```
kubectl create secret tls ess-chat-certificate  --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-matrix-certificate  --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-auth-certificate  --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-well-known-certificate  --cert=path/to/cert/file --key=path/to/key/file
```

In your ess configuration values directory, copy the file `charts/matrix-stack/ci/fragments/quick-setup-certificates.yaml` to `tls.yaml`. Adjust the TLS Secret name accordingly if needed.

### Configuring the database

This is optional but recommended.

You can use the database provided with ESS Community Edition, or use your own PostgreSQL Server. We recommend using a PostgreSQL server installed with your own distribution packages. For a quick set up, feel free to use the included postgres server.

#### Using the internal postgres database

You don't need to do anything. The chart will configure everything automatically for you.

#### Using an existing postgres database

You need to create 2 databases:

- For Synapse [https://element-hq.github.io/synapse/v1.59/postgres.html\#set-up-database](https://element-hq.github.io/synapse/v1.59/postgres.html#set-up-database)

- For MAS [https://element-hq.github.io/matrix-authentication-service/setup/database.html](https://element-hq.github.io/matrix-authentication-service/setup/database.html)


To configure your own Postgres Database in your installation, copy the file `charts/matrix-stack/ci/fragments/quick-setup-postgresql.yaml` to `postgresql.yaml` in your ess configuration values directory and configure it accordingly.

## Installation

Element Server Suite installation is performed using Helm Package Manager, which requires configuration of a values file as specified in the Element Server Suite documentation.

#### Quick setup

For a quick setup using the default settings, copy the file from `charts/matrix-stack/ci/fragments/quick-setup-hostnames.yaml` to `hostnames.yaml` in your ess configuration values directory and edit the hostnames accordingly.

Run the setup using the following helm command. This command supports combining multiple values files depending on your setup. Typically you would pass to the command line a combination of:

- If using Lets Encrypt or Certificate Files : `-f ~/ess-config-values/tls.yaml`
- If using your own PostgreSQL server : `-f ~/ess-config-values/postgresql.yaml`

#### Dev Installation (Temporary)

Create a ghcr.io secret:

```
kubectl create secret -n ess docker-registry ghcr --docker-username=user --docker-password=<github token> --docker-server=ghcr.io
```

Create a values file called ghcr.yaml in your ess configuration values directory for GHCR credentials: 

```
imagePullSecrets:
  - name: ghcr
```

Login helm against ghcr.io:

```
helm registry login -u <github username> ghcr.io
```


Finally, install ess, making sure to use the dev version by adding \--version 0.6.2-dev and including the ghcr.yaml values file:

```
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack --version 0.6.2-dev -f ~/ess-config-values/hostnames.yaml -f ~/ess-config-values/ghcr.yaml <values files to pass> --wait
```

#### Standard Installation

```
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <values files to pass> --wait
```

Wait for the helm command to finish up. ESS is now installed!

#### Create initial user

Element Server Suite Community Edition does not allow user registration by default. To create your initial user, use the “mas-cli manage register-user” command in the Matrix Authentication Service pod :

```
kubectl exec -n ess -it deploy/ess-matrix-authentication-service -- mas-cli manage register-user

Defaulted container "matrix-authentication-service" out of: matrix-authentication-service, render-config (init), db-wait (init), config (init)
✔ Username · alice
User attributes
    	Username: alice
   	Matrix ID: @alice:thisservername.tld
No email address provided, user will be prompted to add one
No password or upstream provider mapping provided, user will not be able to log in

Non-interactive equivalent to create this user:

 mas-cli manage register-user --yes alice

✔ What do you want to do next? (<Esc> to abort) · Set a password
✔ Password · ********
User attributes
    	Username: alice
   	Matrix ID: @alice:thisservername.tld
    	Password: ********
No email address provided, user will be prompted to add one

```

### Verifying the setup

To verify the setup, you should:

* Log into your Element Web client website and log in with the user you created above.
* Verify that Federation works fine using [Matrix Federation Tester](https://federationtester.matrix.org/).
* Login with the Element X mobile client with the user you created above.
* You can use a kubernetes UI client such has [k9s (TUI-Based)](https://k9scli.io/) or [lens (Electron Based)](https://k8slens.dev/) to see your cluster status.

## Configuring Element Server Suite

Element Server Suite Community Edition allows you to configure a lot of values. You will find below the main settings to configure:

#### Configure Element Web client

Element Web configuration is written in JSON. The documentation can be found in the [Element Web repository.](https://github.com/element-hq/element-web/blob/develop/docs/config.md)

To configure Element Web, create a values file with the json config to inject as a string under “additional”:

```
elementWeb:
  additional:
    user-config.json: |
      {
        "some": "settings"
      }
```

#### Configure Synapse

Synapse configuration is written in YAML. The documentation can be found at [here](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html).

```
synapse:
  additional:
    user-config.yaml:
      config: |
        # Add your settings below, taking care of the spacing indentation
        some: settings
```

#### Configure Matrix Authentication Service

Matrix Authentication Service configuration is written in YAML. The documentation can be found [here](https://element-hq.github.io/matrix-authentication-service/reference/configuration.html).

```
matrixAuthenticationService:
  additional:
    user-config.yaml:
      config: |
        # Add your settings below, taking care of the spacing indentation
        some: settings
```

## Advanced configuration

### Values documentation

 The helm chart values documentation is available in:

- The github repository [values files](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/values.yaml).
- The chart [README](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/README.md).
- [Artifacthub.io](https://artifacthub.io/packages/helm/element/matrix-stack).

Configuration samples are available [in the github repository](https://github.com/element-hq/ess-helm/tree/main/charts/matrix-stack/ci).

### Configure storage path when using k3s

`k3s` by default deploys the storage in `/var/lib/rancher/k3s/storage/`. If you want to change the path, you will have to run the k3s setup with the parameter `--default-local-storage-path <your path>`.

### Set up Element Server Suite with k3s on a server with an existing reverse proxy

If your server already has a reverse proxy, ports 80 and 443 will likely be taken.

Use the following command to get the external-ip provisioned by kubernetes for Traefik :

```
kubectl get svc/traefik -n kube-system
NAME      TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE
traefik   LoadBalancer   10.43.184.49   172.20.1.60   80:32100/TCP,443:30129/TCP   5d18h
```


In such a case, you will need to set up K3S with custom ports. Create a file `/var/lib/rancher/k3s/server/manifests/traefik-config.yaml` with the following:

```
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    ports:
      web:
        exposedPort: 8080
      websecure:
        exposedPort: 8443
    service:
      spec:
        externalIPs:
        - `<external IP returned by the command above>`
```

k3s will apply the file content automatically. You can verify its ports using the command :

```
kubectl get svc -n kube-system | grep traefik
traefik          LoadBalancer   10.43.184.49    172.20.1.60   8080:32100/TCP,8443:30129/TCP   5d18h
```

Configure your reverse proxy so that the DNS Names you configured are routed to the external IP of traefik on port 8080 (HTTP) and 8443 (HTTPS).

## Maintenance

### Upgrading

In order to upgrade your deployment, you should:
1. Read the release notes of the new version and check if there are any breaking changes. The file [CHANGELOG.md](./CHANGELOG.md) should be your first stop.
3. Adjust your values if necessary.
2. Re-run the install command. It will upgrade your installation to the latest version of the chart.


### Backups & restore

#### Backups

You need to backup a couple of things to be able to restore your deployment
:
1. The database. You need to backup your database and restore it on a new deployment.
  1. If you are using the provided Postgres database, build a dump using the command `kubectl exec --namespace ess -it sts/ess-postgres -- pg_dumpall -U postgres > dump.sql`. Adjust to your own kubernetes namespace and release name if required.
  2. If you are using your own Postgres database, please build your backup according to your database documentation.
2. Your values files used to deploy the chart
3. The chart will generate some secrets if you do not provide them. To copy them to a local file, you can run the following command: `kubectl get secrets -l "app.kubernetes.io/managed-by=matrix-tools-init-secrets"  -n ess -o yaml > secrets.yaml`. Adjust to your own kubernetes namespace if required.
4. The media files: Synapse stores media in a persistent volume that should be backed up. On a default `k3s` setup, you can find where synapse media is stored on your node using the command `kubectl get pv -n ess -o yaml | grep synapse-media`.

#### Restore

1. Recreate the namespace and the backed-up secret in step 3: 
```
kubectl create ns ess
kubectl apply -f secrets.yaml
```
2. Redeploy the chart using the values backed-up in step 2.
3. Stop Synapse and Matrix Authentication Service workloads:
```
kubectl scale sts -l "app.kubernetes.io/component=matrix-server" -n ess --replicas=0
kubectl scale deploy -l "app.kubernetes.io/component=matrix-authentication" -n ess --replicas=0
```
4. Restore the postgres dump. If you are using the provided Postgres database, this can be achieved using the following commands:
```
# Drop newly created databases and roles
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP DATABASE matrixauthenticationservice'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP DATABASE synapse'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP ROLE synapse_user'
kubectl exec -n ess sts/ess-postgres -- psql -U postgres -c 'DROP ROLE matrixauthenticationservice_user'
kubectl cp dump.sql ess-postgres-0:/tmp -n ess
kubectl exec -n ess sts/ess-postgres -- bash -c "psql -U postgres -d postgres < /tmp/dump.sql"
```
Adjust to your own kubernetes namespace and release name if required.

4. Restore the synapse media files using `kubectl cp` to copy them in Synapse pod. If you are using `k3s`, you can find where the new persistent volume has been mounted with `kubectl get pv -n ess -o yaml | grep synapse-media` and copy your files in the destination path.
5. Run the `helm upgrade --install....` command again to restore your workload's pods.

## Monitoring

The chart provides `ServiceMonitor` automatically to monitor the metrics exposed by ESS.

If your cluster has [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator) or [Victoria Metrics Operator](https://docs.victoriametrics.com/operator/) installed, the metrics will automatically be scraped.

## Uninstall

If you wish to remove ESS from your cluster, you can simply run the following commands to clean up the installation. Please note deleting the `ess` namespace will remove everything within it, including any resources you may have manually created within it:

```
helm uninstall ess -n ess
kubectl delete namespace ess
```

If you want to also uninstall other components installed in this guide, you can do so using the following commands:

```
# Remove cert-manager from cluster
helm uninstall cert-manager -n cert-manager

# Uninstall helm
rm -rf /usr/local/bin/helm $HOME/.cache/helm $HOME/.config/helm $HOME/.local/share/helm

# Uninstall k3s
/usr/local/bin/k3s-uninstall.sh
```
