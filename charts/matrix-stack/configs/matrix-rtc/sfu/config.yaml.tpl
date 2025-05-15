{{- /*
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "matrix-rtc/sfu/config.yaml.tpl missing context" .context -}}

port: 7880
# WebRTC configuration
rtc:
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
  use_external_ip: true

prometheus_port: 6789

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
key_file: /rendered-config/keys.yaml
{{- end }}

# Logging config
logging:
  # log level, valid values: debug, info, warn, error
  level: {{ .logging.level }}
  # log level for pion, default error
  pion_level: {{ .logging.pionLevel }}
  # when set to true, emit json fields
  json: {{ .logging.json }}

# Signal Relay is enabled by default as of v1.5.3

# turn server
turn:
  enabled: false

{{ end }}
