<!--
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Advanced setup

**Contents**
- [Values documentation](#values-documentation)
- [Using a dedicated PostgreSQL database](#using-a-dedicated-postgresql-database)
- [Configuring the storage path when using k3s](#configuring-the-storage-path-when-using-k3s)
- [Monitoring](#monitoring)
- [Components Configuration](#configuration)
   - [Configuring Element Web](#configuring-element-web)
   - [Configuring Synapse](#configuring-synapse)
   - [Configuring Matrix Authentication Service](#configuring-matrix-authentication-service)

## Values documentation

 The Helm chart values documentation is available in:

- The GitHub repository [values files](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/values.yaml).
- The chart [README](https://github.com/element-hq/ess-helm/blob/main/charts/matrix-stack/README.md).
- [Artifacthub.io](https://artifacthub.io/packages/helm/element-server-suite-community/matrix-stack).

Configuration samples are available [in the GitHub repository](https://github.com/element-hq/ess-helm/tree/main/charts/matrix-stack/ci).

### Using a dedicated PostgreSQL database

You need to create 2 databases:

- For Synapse [https://element-hq.github.io/synapse/latest/postgres.html](https://element-hq.github.io/synapse/latest/postgres.html#set-up-database)

- For MAS [https://element-hq.github.io/matrix-authentication-service/setup/database.html](https://element-hq.github.io/matrix-authentication-service/setup/database.html)

To configure your own PostgreSQL Database in your installation, copy the file `charts/matrix-stack/ci/fragments/quick-setup-postgresql.yaml` to `postgresql.yaml` in your ESS configuration values directory and configure it accordingly.

## Configuring the storage path when using K3s

K3s by default deploys the storage in `/var/lib/rancher/k3s/storage/`. If you want to change the path, you will have to run the K3s setup with the parameter `--default-local-storage-path <your path>`.

## Configuring Traefik ingress timeouts when using K3s

If you are experiencing timeouts when uploading large files to ESS, you will want to customize Traefik timeouts creating the file `traefik-config.yaml` in `/var/lib/rancher/k3s/server/manifests`. If the file already exists because you have configured custom ports for Traefik, add the example below to the existing file.

```yml
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    ports:
      web:
        transport:
          respondingTimeouts:
            readTimeout: "<timeout in seconds>s"
            writeTimeout: "<timeout in seconds>s"
            idleTimeout: "<timeout in seconds>s"
      websecure:
        transport:
          respondingTimeouts:
            readTimeout: "<timeout in seconds>s"
            writeTimeout: "<timeout in seconds>s"
            idleTimeout: "<timeout in seconds>s"
```

The above values correspond to the Traefik installation managed by K3s. If you are installing Traefik by other means, the exact structure of the configuration may differ.

## Monitoring

The chart provides `ServiceMonitor` automatically to monitor the metrics exposed by ESS Community.

If your cluster has [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator) or [Victoria Metrics Operator](https://docs.victoriametrics.com/operator/) installed, the metrics will automatically be scraped.

## Configuration

ESS Community allows you to easily configure its individual components. You basically have to create a values file for each component in which you specify your custom configuration. Below you  find sections for each component.

**If you have created new values files for custom configuration, make sure to apply them by passing them with the helm upgrade command (see [Setting up the stack](#setting-up-the-stack)).**

### Configuring Element Web

Element Web configuration is written in JSON. The documentation can be found in the [Element Web repository.](https://github.com/element-hq/element-web/blob/develop/docs/config.md)

To configure Element Web, create a values file with the JSON config to inject as a string under “additional”:

```yml
elementWeb:
  additional:
    user-config.json: |
      {
        "some": "settings"
      }
```

### Configuring Synapse

Synapse configuration is written in YAML. The documentation can be found [here](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html).

```yml
synapse:
  additional:
    user-config.yaml:
      config: |
        # Add your settings below, taking care of the spacing indentation
        some: settings
```

### Configuring Matrix Authentication Service

Matrix Authentication Service configuration is written in YAML. The documentation can be found [here](https://element-hq.github.io/matrix-authentication-service/reference/configuration.html).

```yml
matrixAuthenticationService:
  additional:
    user-config.yaml:
      config: |
        # Add your settings below, taking care of the spacing indentation
        some: settings
```

### Configuring Matrix RTC

Matrix RTC SFU configuration is written in YAML. The documentation can be found [here](https://docs.livekit.io/home/self-hosting/deployment/).

```yml
matrixRTC:
  sfu:
    additional:
      user-config.yaml:
        config: |
          # Add your settings below, taking care of the spacing indentation
          some: settings
```

#### Networking

Matrix RTC SFU will by default advertise the IP resolved after a STUN Request to the Google STUN Servers.

If you want to disable this behaviour, set `useStunToDiscoverPublicIP` to `false` :

```yml
matrixRTC:
  sfu:
    useStunToDiscoverPublicIP: false
```

Without STUN, Matrix RTC will advertise the Host IP as the publicly reachable IP. If your host is behind NAT,
you can configured a manual IP address for the server public IP by setting `manualIP`:

```yml
matrixRTC:
  sfu:
    manualIP: "<your node public IP>"
```
