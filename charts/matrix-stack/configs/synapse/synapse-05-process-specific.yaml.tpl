{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "synapse/synapse-05-process-specific.yaml.tpl missing context" .context }}
worker_app: {{ include "element-io.synapse.process.app" (dict "root" $root "context" .processType) }}

{{- if eq .processType "main" }}
listeners:
{{- else }}
worker_name: ${APPLICATION_NAME}

worker_listeners:
{{- end }}
{{- if (include "element-io.synapse.process.hasHttp" (dict "root" $root "context" .processType)) }}
- port: 8008
  tls: false
  bind_addresses: ['0.0.0.0']
  type: http
  x_forwarded: true
  resources:
  - names:
    - client
    - federation
{{- /* main always loads this if client or federation is set. media-repo workers need it explicitly set.... */}}
{{- if eq .processType "media-repository" }}
    - media
{{- end }}
    compress: false
{{- end }}
{{- if (include "element-io.synapse.process.hasReplication" (dict "root" $root "context" .processType)) }}
- port: 9093
  tls: false
  bind_addresses: ['0.0.0.0']
  type: http
  x_forwarded: false
  resources:
  - names: [replication]
    compress: false
{{- end }}
- type: metrics
  port: 9001
  bind_addresses: ['0.0.0.0']
{{- /* Unfortunately the metrics type doesn't get the health endpoint*/}}
- port: 8080
  tls: false
  bind_addresses: ['0.0.0.0']
  type: http
  x_forwarded: false
  resources:
  - names: [health]
    compress: false

{{- $enabledWorkers := (include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson }}
{{- if (include "element-io.synapse.process.responsibleForMedia" (dict "root" $root "context" (dict "processType" .processType "enabledWorkerTypes" (keys $enabledWorkers)))) }}
enable_media_repo: true
{{- else }}
# Stub out the media storage provider for processes not responsible for media
media_storage_providers:
- module: file_system
  store_local: false
  store_remote: false
  store_synchronous: false
  config:
    directory: "/media/media_store"
{{- end }}
{{- end }}
