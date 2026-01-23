<!--
Copyright 2024-2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- cSpell:disable -->
<p align="center">
<img src="https://img.shields.io/github/check-runs/element-hq/ess-helm/main">
<img alt="GitHub License" src="https://img.shields.io/github/license/element-hq/ess-helm">
<img alt="GitHub Issues or Pull Requests" src="https://img.shields.io/github/v/release/element-hq/ess-helm">
<img alt="GitHub Issues or Pull Requests" src="https://img.shields.io/github/issues/element-hq/ess-helm">
</p>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/images/Element-Server-Suite-Community--dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/assets/images/Element-Server-Suite-Community--light.png">
  <img alt="Element Server Suite Community" width="544">
</picture>
</p>
<!-- cSpell:enable -->

<p align="center">
<b>The official Matrix stack from Element for non-commercial use</b>
</p>

Element Server Suite Community Edition (ESS Community) allows you to deploy a Matrix stack using the provided Helm charts and a Kubernetes distribution of your choice, even if you don't have Kubernetes knowledge. It is provided for non-commercial community use cases with quality in mind and aims to be as easy to use as possible. ESS Community enables you to very quickly deploy a solid Matrix stack fully supporting Matrix 2.0 and gives you the flexibility to make it your own. Below you will find a quick setup guide that gives you everything needed to set up a basic system with as few steps as possible.

# Editions
There are three editions of **Element Server Suite**:

## ESS Community
[ESS Community](https://element.io/server-suite/community) is a cutting-edge Matrix distribution including all the latest features of the Matrix server Synapse and other components. It is freely available under the AGPLv3 license and tailored to small-/mid-scale, non-commercial community use cases with up to 100 users. It's designed to easily and quickly set up a Matrix deployment. It comprises the basic components needed to get you running and is a great way to get started.

To get professional support & upgrade to ESS Pro, [contact Element](https://try.element.io/upgrade-ess-community).

## ESS Pro
[ESS Pro](https://element.io/server-suite/pro) is the commercial backend distribution from Element. It includes everything in ESS Community plus additional features and services that are tailored to professional environments with more than 100 users up to massive scale in the millions. It is designed to support enterprise requirements in terms of advanced IAM, compliance, scalability, high availability and multi-tenancy. ESS Pro makes use of Synapse Pro to provide infrastructure cost savings and improved user experience under high load. It uses Element’s Secure Border Gateway (SBG) as an application layer firewall to manage federation and to ensure that deployments stay compliant at any time. ESS Pro includes L3 support, Long-term Support (LTS), Advanced Security Advisory and prepares you for the Cyber Resilience Act (CRA).

**Additional capabilities with ESS Pro**

Find below an overview of the most important additional product capabilities for professional use with ESS Pro.

- Synapse Pro
  - Resource and operational cost savings (up to 90% compared to Community, depending on usage patterns)
    - Multi-tenancy (for running many small hosts)
    - More efficient and cloud-native Synapse subsystems (for running individual large hosts)
  - Dynamic and automatic scaling with adaptation to actual load (horizontal and vertical)
  - In-cluster high availability (HA)
  - Improved end-user experience due to better stability and resilience under load
- Application-level firewall with federation controls and more (Secure Border Gateway)
- User lifecycle management and group access control via LDAP/SCIM (Advanced IAM)
- Malware scanning of media attachments (Content Scanner)
- Auditing (AuditBot)
- Supervision and central control (AdminBot)
- LDAP support for user authentication
- S3 support for media storage
- Distroless/minimal images of all relevant core components

A full comparison between the editions can be found [here](https://element.io/pricing). See the [ESS Pro documentation](https://docs.element.io/latest/element-server-suite-pro/introduction-to-ess-pro/) for more details.

## ESS TI-M
[ESS TI-M](https://element.io/server-suite/ti-messenger) is a special version of ESS Pro focused on the requirements of TI-Messenger Pro and ePA as specified by the German National Digital Health Agency Gematik. It complies with a specific Matrix version and does not make use of experimental features.

# Contents

- [Architecture and components](#architecture-and-components)
- [Feedback and questions](#feedback-and-questions)
- [Getting started](#getting-started)
   - [Resource requirements](#resource-requirements)
   - [Prerequisites](#prerequisites)
- [Quick setup](#installation)
  - [Preparing the environment](#preparing-the-environment)
    - [DNS](#dns)
    - [K3S - Kubernetes single node setup](#kubernetes-single-node-setup-with-k3s)
    - [Certificates](#certificates)
        - [Let's Encrypt](#lets-encrypt)
        - [Certificate File](#certificate-file)
          - [Wildcard certificate](#wildcard-certificate)
          - [Individual certificates](#individual-certificates)
        - [Using an existing reverse proxy](#using-an-existing-reverse-proxy)
          - [Example configurations](#example-configurations)
    - [Configuring the database](#configuring-the-database)
  - [Installation](#installation)
    - [Setting up the stack](#setting-up-the-stack)
    - [Creating an initial user](#creating-an-initial-user)
    - [Verifying the setup](#verifying-the-setup)
- [Advanced setup](#advanced-setup)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Uninstalling](#uninstalling)

# Architecture and components

<!-- cSpell:disable -->
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/images/ESS-Community-architecture--dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/assets/images/ESS-Community-architecture--light.png">
  <img alt="ESS Community Diagram" width="676">
</picture>
</p>
<!-- cSpell:enable -->

ESS Community comes with the following components out-of-the box:

- [Synapse](https://github.com/element-hq/synapse): The Matrix server
- [Matrix Authentication Service](https://github.com/element-hq/matrix-authentication-service): Manages users and handles user authentication.
- [Element Call's Matrix RTC Backend](https://github.com/element-hq/element-call/tree/livekit): Allows to use Element Call from Element X and Element Web apps.
- [Element Web](https://github.com/element-hq/element-web): The Matrix Web Client provided by Element.
- [Element Admin](https://github.com/element-hq/element-admin): The Admin Console provided by Element.
- [Hookshot](https://github.com/matrix-org/hookshot): A Matrix bot for connecting to external services like GitHub, GitLab, JIRA, and more.
- PostgreSQL: An optional packaged PostgreSQL server that allows you to quickly set up the stack out-of-the-box. For a better long-term experience, please consider using a dedicated PostgreSQL server. See the [advanced setup docs](./docs/advanced.md) for more information.
- HAProxy: Provides the routing to Synapse processes.
- .well-known delegation: Required for federation and Matrix clients.

It is possible to enable/disable each on a per-component basis. They can also be customized using dedicated values.

For more details about the architecture, please refer to the [Architecture Documentation](docs/architecture.md).

# Feedback and questions
Element does not provide support for ESS Community but we want to know about your experience and get any suggestions for improvements that you might have. Any contribution helps to further improve the stack and its documentation.

If you have feedback or questions about it, you can
- Create a ticket in the [issue tracker](https://github.com/element-hq/ess-helm/issues)
- Join our [ESS Community Matrix room](https://matrix.to/#/#ess-community:element.io)

If you want to suggest changes to the distribution or contribute them yourself, please come and chat to us first in #ess-community:element.io to coordinate.

---

# Getting started

This readme is primarily aimed as a simple walkthrough to set up ESS Community.
Users experienced with Helm and Kubernetes can refer directly to the chart README at [charts/matrix-stack/README.md](charts/matrix-stack/README.md).

## Resource requirements

The quick setup relies on K3s. It requires at least 2 CPU cores and 2 GB of memory available.

## Prerequisites

You first need to choose what your server name is going to be. The server name makes up the latter part of a user's Matrix ID. In the following example Matrix ID, `server-name.tld` is the server name, and should point to your ESS Community installation:

  `@alice:server-name.tld`

**It is currently not possible to change your server name without resetting your database and having to recreate the server.**

# Quick setup

Setting up a basic environment involves only **6 steps**:

1. [Setting up DNS entries](#dns)
2. [Setting up K3s](#kubernetes-single-node-setup-with-k3s) (or use another Kubernetes distribution)
3. [Setting up TLS/certificates](#certificates)
4. [Installing the stack](#installation)
5. [Creating an initial user](#creating-an-initial-user)
6. [Verifying the setup](#verifying-the-setup)

The below instructions will guide you through each of the steps.

## Preparing the environment

### DNS

You need to create DNS records (A or CNAME, for example) to set up ESS Community. All of these DNS entries must point to your server's IP.

- Server name: This DNS entry must point to the installation ingress. It must be the `server-name.tld` you chose above.
- Synapse: For example, you could use `matrix.<server-name.tld>`.
- Matrix Authentication Service: For example, you could use `account.<server-name.tld>`.
- Matrix RTC Backend: For example, you could use `mrtc.<server-name.tld>`.
- Element Web: This will be the address of the chat client of your server. For example, you could use `chat.<server-name.tld>`.
- Element Admin: This will be the address of the admin client of your server. For example, you could use `admin.<server-name.tld>`.

### Ports

For this simple setup you need to open the following ports:
 - TCP 80: This port will be used for the HTTP connections of all services, which will redirect to the HTTPS connection.
 - TCP 443: This port will be used for the HTTPS connections of all services.
 - TCP 30881: This port will be used for the TCP WebRTC connections of Matrix RTC Backend.
 - UDP 30882: This port will be used for the Muxed WebRTC connections of Matrix RTC Backend.

These ports will be exposed by default on a running ESS Community deployment. You can change that as needed, for instance if you have another service occupying 80/443. See the [Using an existing reverse proxy](#using-an-existing-reverse-proxy) section below.

### Kubernetes single node setup with K3s

This guide suggests using K3s as the Kubernetes node hosting ESS Community. Other options are possible. You can use an existing Kubernetes cluster, or use other clusters like [`microk8s`](https://microk8s.io/). Any Kubernetes distribution is compatible with ESS Community, so choose one according to your needs.

The following will install K3s on the node, and configure its Traefik proxy automatically. If you want to configure K3s behind an existing reverse proxy on the same node, please see the [dedicated section](#using-an-existing-reverse-proxy).

If you have a firewall running on your server, please follow the [K3s official recommendations](https://docs.k3s.io/installation/requirements?os=debian#operating-systems).
1. Run the following command to install K3s:

```
curl -sfL https://get.k3s.io | sh -
```

2. Once K3s is set up, copy its `kubeconfig` to your home directory to get access to it:

```
mkdir ~/.kube
export KUBECONFIG=~/.kube/config
sudo k3s kubectl config view --raw > "$KUBECONFIG"
chmod 600 "$KUBECONFIG"
chown "$USER:$USER" "$KUBECONFIG"
```

3. Add `export KUBECONFIG=~/.kube/config` to `~/.bashrc` to make it persistent

4. Install Helm, the Kubernetes Package Manager. You can use your [OS repository](https://helm.sh/docs/intro/install/) or call the following command:

```
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

5. Create your Kubernetes namespace where you will deploy the Element Server Suite Community:

```
kubectl create namespace ess
```

6. Create a directory containing your Element Server Suite configuration values:

```
mkdir ~/ess-config-values
```

### Certificates

We present here 3 options to set up certificates in Element Server Suite. 

- Option 1: [Using Let's Encrypt to automatically issue new certificates](#lets-encrypt)
- Option 2: [Using existing certificate files](#certificate-file)
- Option 3: [Using an existing reverse proxy](#using-an-existing-reverse-proxy)

To configure Element Server Suite behind an existing reverse proxy already serving TLS, you can [jump to the end of this section](#using-an-existing-reverse-proxy).

#### Let's Encrypt

To use Let’s Encrypt with ESS Community, you should use [Cert Manager](https://cert-manager.io/). This is a Kubernetes component which allows you to get certificates issued by an ACME provider. The installation follows the [official manual](https://cert-manager.io/docs/installation/helm/):

1. Add Helm Jetstack repository:

```
helm repo add jetstack https://charts.jetstack.io --force-update
```

2. Install Cert-Manager:

```
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.17.0 \
  --set crds.enabled=true
```

3. Configure Cert-Manager to allow ESS Community to request Let’s Encrypt certificates automatically. Create a `ClusterIssuer` resource in your K3s node to do so:

```
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod-private-key
    solvers:
      - http01:
          ingress:
            class: traefik
EOF
```

4. In your ESS configuration values directory, copy the file [`charts/matrix-stack/ci/fragments/quick-setup-letsencrypt.yaml`](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/ci/fragments/quick-setup-letsencrypt.yaml) to `tls.yaml`.

```
curl -L https://raw.githubusercontent.com/element-hq/ess-helm/main/charts/matrix-stack/ci/fragments/quick-setup-letsencrypt.yaml -o ~/ess-config-values/tls.yaml
```

#### Certificate File

##### Wildcard certificate

If your wildcard certificate covers both the server-name and the hosts of your services, you can use it directly.

1. Import your certificate file in your namespace using [kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_tls/):

```
kubectl create secret tls ess-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
```

2. In your ess configuration values directory, copy the file '[charts/matrix-stack/ci/fragments/quick-setup-wildcard-cert.yaml](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/ci/fragments/quick-setup-wildcard-cert.yaml)' to `tls.yaml`. Adjust the TLS Secret name accordingly if needed.

```
curl -L https://raw.githubusercontent.com/element-hq/ess-helm/refs/heads/main/charts/matrix-stack/ci/fragments/quick-setup-wildcard-cert.yaml -o ~/ess-config-values/tls.yaml
```

##### Individual certificates

1. If you have a distinct certificate for each of your DNS names, you will need to import each certificate in your namespace using [kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_tls/):
```
kubectl create secret tls ess-admin-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-chat-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-matrix-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-auth-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-mrtc-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
kubectl create secret tls ess-well-known-certificate -n ess --cert=path/to/cert/file --key=path/to/key/file
```

2. In your ess configuration values directory, copy the file '[charts/matrix-stack/ci/fragments/quick-setup-certificates.yaml](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/ci/fragments/quick-setup-certificates.yaml)' to `tls.yaml`. Adjust the TLS Secret name accordingly if needed.

```
curl -L https://raw.githubusercontent.com/element-hq/ess-helm/refs/heads/main/charts/matrix-stack/ci/fragments/quick-setup-certificates.yaml -o ~/ess-config-values/tls.yaml
```

#### Using an existing reverse proxy

If your server already has a reverse proxy, ports 80 and 443 will likely be taken.

1. Use the following command to get the external-ip provisioned by Kubernetes for Traefik :

```
kubectl get svc/traefik -n kube-system
NAME      TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE
traefik   LoadBalancer   10.43.184.49   172.20.1.60   80:32100/TCP,443:30129/TCP   5d18h
```


2. In such a case, you will need to set up K3S with custom ports. Create a file `/var/lib/rancher/k3s/server/manifests/traefik-config.yaml` with the following:

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

3. K3s will apply the file content automatically. You can verify its ports using the command :

```
kubectl get svc -n kube-system | grep traefik
traefik          LoadBalancer   10.43.184.49    172.20.1.60   8080:32100/TCP,8443:30129/TCP   5d18h
```

4. Configure your reverse proxy so that the DNS names you configured are routed to the external IP of Traefik on port 8080 (HTTP) and 8443 (HTTPS).

5. If the certificates are handled in your reverse proxy, you can point to port 8080 (HTTP) only and disable TLS in ESS. Copy the file '[charts/matrix-stack/ci/fragments/quick-setup-external-cert.yaml](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/ci/fragments/quick-setup-external-cert.yaml)' to `tls.yaml`.

```
curl -L https://raw.githubusercontent.com/element-hq/ess-helm/refs/heads/main/charts/matrix-stack/ci/fragments/quick-setup-external-cert.yaml -o ~/ess-config-values/tls.yaml
```

##### Example configurations
To make running ESS Community behind a reverse proxy as easy as possible, you can find below some configuration examples for popular web servers.

<details><summary>Apache2</summary>

Find below a minimal example of an Apache2 vhost to work as a reverse proxy with TLS termination for ESS Community. You will need to enable the respective modules in your Apache2 configuration.

```
<VirtualHost *:*>
  ServerName <your domain/subdomain>
  SSLEngine on
  SSLCertificateFile /path/to/your/certfile
  SSLCertificateKeyFile /path/to/your/keyfile
  SSLCipherSuite ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256
  SSLHonorCipherOrder on
  SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
  Header unset Strict-Transport-Security
  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"

  ProxyPreserveHost On
  ProxyPass / http://127.0.0.1:8080/ nocanon
  ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>
```
</details>

<details><summary>Nginx</summary>

Below is a simple, but complete example of a Nginx reverse proxy config for ESS Community with TLS termination.
```
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    access_log /var/log/nginx/ess.log main;
    error_log /var/log/nginx/ess.errors;

    ssl_certificate /etc/nginx/certs/certificate.full;
    ssl_certificate_key /etc/nginx/certs/certificate.key;

    #TLSv1.2 is required for iOS support for now
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_dhparam /etc/nginx/dhparam.pem;
    ssl_session_cache shared:le_nginx_SSL:10m;
    ssl_session_timeout 1440m;
    ssl_session_tickets off;
    ssl_buffer_size 4k;
    ssl_stapling on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains; preload' always;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:DHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers on;

    server_name chat.example.com matrix.example.com account.example.com mrtc.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;

        client_max_body_size 50M;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name chat.example.com matrix.example.com account.example.com mrtc.example.com;
    return 301 https://$host$request_uri;
}

```
</details>

### Configuring the database

You can either use the database provided with ESS Community or you use a dedicated PostgreSQL Server. We recommend [using a PostgreSQL server](./docs/advanced.md#using-a-dedicated-postgresql-database) installed with your own distribution packages. For a quick set up, feel free to use the internal PostgreSQL database, which the chart will configure automatically for you by default with no required configuration.

## Installation

The ESS Community installation is performed using Helm package manager, which requires configuration of a values file as specified in this documentation.

### Setting up the stack

For a quick setup using the default settings, copy the file from '[charts/matrix-stack/ci/fragments/quick-setup-hostnames.yaml](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/ci/fragments/quick-setup-hostnames.yaml)' to `hostnames.yaml` in your ESS configuration values directory and edit the hostnames accordingly.

```
curl -L https://raw.githubusercontent.com/element-hq/ess-helm/refs/heads/main/charts/matrix-stack/ci/fragments/quick-setup-hostnames.yaml -o ~/ess-config-values/hostnames.yaml
```

Run the setup using the following helm command. This command supports combining multiple values files depending on your setup. Typically you would pass to the command line a combination of:

- If using Lets Encrypt or Certificate Files: `-f ~/ess-config-values/tls.yaml`
- If using your own, external PostgreSQL server: `-f ~/ess-config-values/postgresql.yaml`
  - If you wish to use the PostgresSQL server installed and managed by the chart, no additional values file or configuration is required

**Each optional additional values file used needs to be prefixed with `-f `**

```
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f ~/ess-config-values/hostnames.yaml <optional additional values files to pass> --wait
```

Wait for the helm command to finish up. ESS Community is now installed!

### Creating an initial user

ESS Community does not allow user registration by default. To create your initial user, use the `mas-cli manage register-user` command in the Matrix Authentication Service pod:

```
kubectl exec -n ess -it deploy/ess-matrix-authentication-service -- mas-cli manage register-user
```

This should give you the following output:

```
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

#### Allowing users registration

To allow users registration, you will need to configure MAS with SMTP.
To do so, follow the steps in [Configuring Matrix Authentication Service](./docs/advanced.md#configuring-matrix-authentication-service) to inject additional [email configuration](https://element-hq.github.io/matrix-authentication-service/reference/configuration.html#email).

### Verifying the setup

To verify the setup, you can:

* Log into your Element Web client website and log in with the user you created above.
* Verify that federation works fine using [Matrix Federation Tester](https://federationtester.matrix.org/).
* Login with an Element X mobile client with the user you created above.
* You can use a Kubernetes UI client such has [k9s (TUI-Based)](https://k9scli.io/) or [lens (Electron Based)](https://k8slens.dev/) to see your cluster status.

# Advanced setup

For advanced setup instructions, please refer to the [Advanced setup](docs/advanced.md) guide.

# Troubleshooting

For common troubleshooting queries, please refer to the [Troubleshooting](docs/troubleshooting.md) guide.

# Maintenance

For maintenance topics like upgrading, backups and restoring from backups, please refer to the [Maintenance](docs/maintenance.md) guide.

# Uninstalling

If you wish to remove ESS Community from your cluster, you can simply run the following commands to clean up the installation.

```sh
helm uninstall ess -n ess
# If initSecrets is enabled, you may need to delete this
kubectl delete secrets/ess-generated -n ess
# If deploymentMarkers is enabled, you may need to delete this
kubectl delete configmap/ess-deployment-markers -n ess
# If synapse is enabled, you may need to delete this
kubectl delete pvc/ess-synapse-media -n ess
# If postgres is enabled and either synapse or matrixAuthenticationService is enabled, you may need to delete this
kubectl delete pvc/ess-postgres-data -n ess
```

Alternatively you can delete the whole `ess` namespace which will remove everything within it, including any resources you may have manually created within it:

```sh
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

# (Optional) Remove config
rm -rf ~/ess-config-values ~/.kube
```
