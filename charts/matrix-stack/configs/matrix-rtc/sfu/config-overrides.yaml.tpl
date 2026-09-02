{{- /*
Copyright 2024-2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "matrix-rtc/sfu/config.yaml.tpl missing context" .context -}}

port: 7880

prometheus:
  port: 6789

# Logging config
logging:
  # log level, valid values: debug, info, warn, error
  level: {{ .logging.level }}
  # log level for pion, default error
  pion_level: {{ .logging.pionLevel }}
  # when set to true, emit json fields
  json: {{ .logging.json }}

# WebRTC configuration
rtc:
  use_external_ip: {{ .useStunToDiscoverPublicIP }}
{{ if or .manualIP (not .useStunToDiscoverPublicIP) }}
  node_ip: ${NODE_IP}
{{- end }}
{{- with .exposedServices }}
{{- with .rtcTcp }}
{{- if .enabled }}
  tcp_port: {{ .port }}
{{- end }}
{{- end }}
{{- with .rtcMuxedUdp }}
{{- if .enabled }}
  udp_port: {{ .port }}
{{- end }}
{{- end }}
{{- with .rtcUdp }}
{{- if .enabled }}
  port_range_start: {{ .portRange.startPort }}
  port_range_end: {{ .portRange.endPort }}
{{- end }}
{{- end }}
{{ end }}

key_file: /conf/keys.yaml

{{- if or .exposedServices.turnTLS.enabled .exposedServices.turn.enabled }}
turn:
  enabled: true
{{- with .exposedServices.turnTLS }}
{{ if .enabled }}
{{- if eq .portType "HostPort" }}
  tls_port: {{ .port }}
{{- else }}
  tls_port: 5349
{{- end }}
  domain: {{ tpl .domain $root }}
{{- if .tlsTerminationOnPod }}
  cert_file: /turn-tls/tls.crt
  key_file: /turn-tls/tls.key
{{- end }}
  external_tls: {{ not .tlsTerminationOnPod }}
{{- end }}
{{- end }}
{{- with .exposedServices.turn }}
{{ if .enabled }}
  udp_port: {{ .port }}
{{- end }}
{{- end }}
{{- end }}

redis:
{{- if .redis }}
  address: {{ tpl .redis.host $root }}:{{ .redis.port | default 6379 }}
{{- with .redis.db }}
  db: {{ . }}
{{- end }}
{{- if .redis.password }}
  password: ${SFU_REDIS_PASSWORD}
{{- end }}
{{- else }}
  address: "{{ $root.Release.Name }}-valkey.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:6379"
  db: 3
{{- end }}

room:
  auto_create: false

webhook:
  api_key: {{ $root.Values.matrixRTC.livekitAuth.key }}

  urls:
  - http://{{ $root.Release.Name }}-matrix-rtc-authorisation-service.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:8080/sfu_webhook
{{ end }}
