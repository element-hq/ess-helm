{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "matrix-rtc/sfu/config.yaml.tpl missing context" .context -}}

{{- /* TODO: Move me to overrides after 25.10 is out. */ -}}
rtc:
  use_external_ip: {{ .useStunToDiscoverPublicIP }}
{{ if or .manualIP (not .useStunToDiscoverPublicIP) }}
  node_ip: ${NODE_IP}
{{- end }}
# turn server
turn:
  enabled: false

{{ end }}
