{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "synapse/synapse-05-process-specific.yaml.tpl missing context" .context }}
{{- $isHook := required "synapse/synapse-05-process-specific.yaml.tpl requires context.isHook" .isHook -}}
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
  bind_addresses:
{{- /* Do not be tempted to reorder, Synapse allows 0.0.0.0 to fail IFF the address is already bound and :: is in the list */}}
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
  - "::"
{{- end }}
{{- if has $root.Values.networking.ipFamily (list "ipv4" "dual-stack") }}
  - "0.0.0.0"
{{- end }}
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
  bind_addresses:
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
  - "::"
{{- end }}
{{- if has $root.Values.networking.ipFamily (list "ipv4" "dual-stack") }}
  - "0.0.0.0"
{{- end }}
  type: http
  x_forwarded: false
  resources:
  - names: [replication]
    compress: false
{{- end }}
- type: metrics
  port: 9001
  bind_addresses:
{{- /* This is different to the others and doesn't currently handle the address being in-use. We bind :: and rely on the lack of IPV6_V6ONLY on the scoket options */}}
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
  - "::"
{{- else }}
  - "0.0.0.0"
{{- end }}
{{- /* Unfortunately the metrics type doesn't get the health endpoint*/}}
- port: 8080
  tls: false
  bind_addresses:
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
  - "::"
{{- end }}
{{- if has $root.Values.networking.ipFamily (list "ipv4" "dual-stack") }}
  - "0.0.0.0"
{{- end }}
  type: http
  x_forwarded: false
  resources:
  - names: [health]
    compress: false

{{- $enabledWorkers := (include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson }}
{{- if (include "element-io.synapse.process.responsibleForMedia" (dict "root" $root "context" (dict "processType" .processType "enabledWorkerTypes" (keys $enabledWorkers)))) }}
# This is still required despite media_storage_providers as otherwise Synapse attempts to mkdir media_store at the root of the container
{{- /* The check config job tries to write the media_store directory, it fails as it does not mount the PVC.
       This workaround will make it create the media_store directory in /tmp
*/}}
media_store_path: "{{ if $isHook }}/tmp/{{ else }}/media/{{ end }}media_store"
enable_media_repo: true
{{- else }}
# This is still required despite media_storage_providers as otherwise Synapse attempts to mkdir media_store at the root of the container
media_store_path: "/tmp/media_store"
enable_local_media_storage: false
{{- end }}
{{- end }}
