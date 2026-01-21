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

{{- if (.livekitAuth).keysYaml -}}
key_file: /secrets/{{ (printf "/secrets/%s"
      (include "element-io.ess-library.provided-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitAuth.keysYaml"
              "defaultSecretName" (printf "%s-matrix-rtc-authorisation-service" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_KEYS_YAML"
              )
        ))) }}
{{- else }}
key_file: /conf/keys.yaml
{{- end }}

{{- if or .exposedServices.turnTLS.enabled .exposedServices.turn.enabled }}
turn:
  enabled: true
{{- with .exposedServices.turnTLS }}
{{ if .enabled }}
  tls_port: {{ .port }}
  domain: {{ tpl .domain $root }}
  cert_file: /turn-tls/tls.crt
  key_file: /turn-tls/tls.key
{{- end }}
{{- end }}
{{- with .exposedServices.turn }}
{{ if .enabled }}
  udp_port: {{ .port }}
{{- end }}
{{- end }}
{{- end }}

room:
  auto_create: false

{{ end }}
