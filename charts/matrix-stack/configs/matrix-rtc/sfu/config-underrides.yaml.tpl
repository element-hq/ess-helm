{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "matrix-rtc/sfu/config.yaml.tpl missing context" .context -}}

{{- /* TODO: Move me to overrides after 25.10 is out. */ -}}
rtc:
  use_external_ip: {{ .useStunToDiscoverPublicIP }}
{{ if .manualIP }}
  # To workaround https://github.com/livekit/livekit/issues/2088
  # Any IP address is acceptable, it doesn't need to be a correct one,
  # it just needs to be present to get LiveKit to skip checking all local interfaces
  # We assign here a TEST-NET IP which is
  # overridden by the NODE_IP env var at runtime
  node_ip: 198.51.100.1
{{- end }}
# turn server
turn:
  enabled: false

{{ end }}
