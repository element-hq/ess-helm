{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}

# A map file that is used in haproxy config to map from matrix paths to the
# named backend. The format is: path_regexp backend_name
{{ if dig "client-reader" "enabled" false $root.Values.synapse.workers }}
^/_matrix/client/(api/v1|r0|v3|unstable)/pushrules/ client-reader
^/_matrix/client/unstable/org.matrix.msc4140/delayed_events client-reader
^/_matrix/client/(api/v1|r0|v3|unstable)/devices/ client-reader
{{- end }}
{{ if dig "sso-login" "enabled" false $root.Values.synapse.workers }}
{{- if (and $root.Values.matrixAuthenticationService.enabled (not $root.Values.matrixAuthenticationService.preMigrationSynapseHandlesAuth)) }}
^/_synapse/admin/v1/users/[^/]+/devices$ sso-login
{{- end }}
{{- end }}
