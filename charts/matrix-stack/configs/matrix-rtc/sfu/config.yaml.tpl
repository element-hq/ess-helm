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
{{ if .useExternalIp }}
  use_external_ip: true
{{- else }}
  use_external_ip: false
  # To workaround https://github.com/livekit/livekit/issues/2088
  # Any IP address is acceptable, it doesn't need to be a correct one,
  # it just needs to be present to get LiveKit to skip checking all local interfaces
  # We assign here a TEST-NET IP which is
  # overridden by the NODE_IP env var at runtime
  node_ip: 198.51.100.1
{{- end }}
{{- with .stunServers }}
  stun_servers:
  {{ . | toYaml | nindent 4 }}
{{- end }}

prometheus_port: 6789

key_file: /rendered-config/keys.yaml

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
