{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "synapse/synapse-04-homeserver-overrides.yaml.tpl missing context" .context }}
{{- $isHook := required "element-io.synapse.config.shared-overrides requires context.isHook" .isHook -}}
public_baseurl: https://{{ tpl .ingress.host $root }}/
server_name: {{ tpl $root.Values.serverName $root }}
signing_key_path: /secrets/{{
  include "element-io.ess-library.init-secret-path" (
    dict "root" $root "context" (
      dict "secretPath" "synapse.signingKey"
           "initSecretKey" "SYNAPSE_SIGNING_KEY"
           "defaultSecretName" (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook)))
           "defaultSecretKey" "SIGNING_KEY"
      )
    ) }}
enable_metrics: true
log_config: "/conf/log_config.yaml"
macaroon_secret_key_path:  /secrets/{{
  include "element-io.ess-library.init-secret-path" (
    dict "root" $root "context" (
      dict "secretPath" "synapse.macaroon"
           "initSecretKey" "SYNAPSE_MACAROON"
           "defaultSecretName" (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook)))
           "defaultSecretKey" "MACAROON"
      )
    ) }}
registration_shared_secret_path: /secrets/{{
  include "element-io.ess-library.init-secret-path" (
    dict "root" $root "context" (
      dict "secretPath" "synapse.registrationSharedSecret"
           "initSecretKey" "SYNAPSE_REGISTRATION_SHARED_SECRET"
           "defaultSecretName" (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook)))
           "defaultSecretKey" "REGISTRATION_SHARED_SECRET"
      )
    ) }}

database:
  name: psycopg2
  args:
{{- if .postgres }}
    user: {{ .postgres.user }}
    password: ${SYNAPSE_POSTGRES_PASSWORD}
    database: {{ .postgres.database }}
    host: {{ (tpl .postgres.host $root) }}
    port: {{ .postgres.port | default 5432 }}
    sslmode: {{ .postgres.sslMode | default "prefer" }}
{{- else if $root.Values.postgres.enabled }}
    user: "synapse_user"
    password: ${SYNAPSE_POSTGRES_PASSWORD}
    database: "synapse"
    host: "{{ $root.Release.Name }}-postgres.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}"
    port: 5432
    sslmode: prefer
{{ end }}

    application_name: ${APPLICATION_NAME}
    keepalives: 1
    keepalives_idle: 10
    keepalives_interval: 10
    keepalives_count: 3

# The default as of 1.27.0
ip_range_blacklist:
- '127.0.0.0/8'
- '10.0.0.0/8'
- '172.16.0.0/12'
- '192.168.0.0/16'
- '100.64.0.0/10'
- '192.0.0.0/24'
- '169.254.0.0/16'
- '192.88.99.0/24'
- '198.18.0.0/15'
- '192.0.2.0/24'
- '198.51.100.0/24'
- '203.0.113.0/24'
- '224.0.0.0/4'
- '::1/128'
- 'fe80::/10'
- 'fc00::/7'
- '2001:db8::/32'
- 'ff00::/8'
- 'fec0::/10'

{{- if (include "element-io.matrix-authentication-service.readyToHandleAuth" (dict "root" $root)) }}
matrix_authentication_service:
  enabled: true
  secret_path: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "matrixAuthenticationService.synapseSharedSecret"
                        "initSecretKey" "MAS_SYNAPSE_SHARED_SECRET"
                        "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .))
                        "defaultSecretKey" "SYNAPSE_SHARED_SECRET"
                      )
                  ) }}
  endpoint: http://{{ $root.Release.Name }}-matrix-authentication-service.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:8080/
{{- end }}

{{- if or (include "element-io.matrix-authentication-service.readyToHandleAuth" (dict "root" $root)) $root.Values.matrixRTC.enabled }}
experimental_features:
{{- if $root.Values.matrixRTC.enabled }}
  # MSC3266: Room summary API. Used for knocking over federation
  msc3266_enabled: true
  # MSC4222 needed for syncv2 state_after. This allow clients to
  # correctly track the state of the room.
  msc4222_enabled: true
{{- end }}

{{- if (include "element-io.matrix-authentication-service.readyToHandleAuth" (dict "root" $root)) }}
  # QR Code Login. Requires MAS
  msc4108_enabled: true
password_config:
  localdb_enabled: false
  enabled: false
{{- end }}
{{- end }}

{{- if dig "appservice" "enabled" false .workers }}

notify_appservices_from_worker: {{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "appservice") }}-0
{{- end }}

{{- with .appservices }}
app_service_config_files:
{{- range $idx, $appservice := . }}
{{- if $appservice.configMap }}
 - /as/{{ $idx }}/{{ $appservice.configMapKey }}
{{- else }}
 - /as/{{ $idx }}/{{ $appservice.secretKey }}
{{- end }}
{{- end }}
{{- end }}

{{- if dig "background" "enabled" false .workers }}

run_background_tasks_on: {{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "background") }}-0
{{- end }}

{{- if dig "federation-sender" "enabled" false .workers }}

send_federation: false
federation_sender_instances:
{{- range $index := untilStep 0 ((index .workers "federation-sender").replicas | int) 1 }}
- {{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "federation-sender") }}-{{ $index }}
{{- end }}
{{- else }}

send_federation: true
{{- end }}

# This is still required despite media_storage_providers as otherwise Synapse attempts to mkdir /media_store
media_store_path: "/media/media_store"
max_upload_size: "{{ .media.maxUploadSize }}"
{{- if dig "media-repository" "enabled" false .workers }}
media_instance_running_background_jobs: "{{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "media-repository") }}-0"
{{- end }}

{{- if dig "pusher" "enabled" false .workers }}

start_pushers: false
pusher_instances:
{{- range $index := untilStep 0 ((index .workers "pusher").replicas | int) 1 }}
- {{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "pusher") }}-{{ $index }}
{{- end }}
{{- else }}

start_pushers: true
{{- end }}

{{- if dig "user-dir" "enabled" false .workers }}

update_user_directory_from_worker: {{ $root.Release.Name }}-synapse-{{- include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" "user-dir") }}-0
{{- end }}
{{- $enabledWorkers := (include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson }}

instance_map:
  main:
    host: {{ $root.Release.Name }}-synapse-main.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}
    port: 9093
{{- range $workerType, $workerDetails := $enabledWorkers }}
{{- if include "element-io.synapse.process.hasReplication" (dict "root" $root "context" $workerType) }}
{{- $workerTypeName := include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" $workerType) }}
{{- range $index := untilStep 0 ($workerDetails.replicas | int | default 1) 1 }}
  {{ $root.Release.Name }}-synapse-{{ $workerTypeName }}-{{ $index }}:
    host: {{ $root.Release.Name }}-synapse-{{ $workerTypeName }}-{{ $index }}.{{ $root.Release.Name }}-synapse-{{ $workerTypeName }}.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}
    port: 9093
{{- end }}
{{- end }}
{{- end }}

{{- if $enabledWorkers }}

redis:
  enabled: true
  host: "{{ $root.Release.Name }}-synapse-redis.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}"
{{- if include "element-io.synapse.streamWriterWorkers" (dict "root" $root) | fromJsonArray }}

stream_writers:
{{- range $workerType, $workerDetails := $enabledWorkers }}
{{- if include "element-io.synapse.process.streamWriters" (dict "root" $root "context" $workerType) | fromJsonArray }}
{{- $workerTypeName := include "element-io.synapse.process.workerTypeName" (dict "root" $root "context" $workerType) }}
{{- range $stream_writer := include "element-io.synapse.process.streamWriters" (dict "root" $root "context" $workerType) | fromJsonArray }}
  {{ $stream_writer }}:
{{- range $index := untilStep 0 ($workerDetails.replicas | int | default 1) 1 }}
  - {{ $root.Release.Name }}-synapse-{{ $workerTypeName }}-{{ $index }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
