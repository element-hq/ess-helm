{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root }}
{{- with required "matrix-authentication-service/config.yaml.tpl missing context" .context }}
policy:
  data:
    admin_clients: []
    admin_users: []
    client_registration:
      allow_host_mismatch: false
      allow_insecure_uris: false

experimental:
  session_limit:
    soft_limit: 50
    hard_limit: 50
{{- end -}}
