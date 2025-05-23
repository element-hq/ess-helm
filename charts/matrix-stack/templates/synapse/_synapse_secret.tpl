{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.synapse.secret-name" }}
{{- $root := .root }}
{{- with required "element-io.synapse.secret-name requires context" .context }}
{{- $isHook := required "element-io.synapse.secret-name requires context.isHook" .isHook }}
{{- if $isHook }}
{{- $root.Release.Name }}-synapse-hook
{{- else }}
{{- $root.Release.Name }}-synapse
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.secret-data" }}
{{- $root := .root }}
{{- with required "element-io.synapse.secret-data requires context" .context }}
data:
{{- with .additional }}
{{- range $key := (. | keys | uniq | sortAlpha) }}
{{- $prop := index $root.Values.synapse.additional $key }}
{{- if $prop.config }}
  user-{{ $key }}: {{ $prop.config | b64enc }}
{{- end }}
{{- end }}
{{- end }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "synapse.macaroon" "initIfAbsent" true)) -}}
{{- with .macaroon.value }}
  MACAROON: {{ . | b64enc }}
{{- end }}
{{- with (.postgres).password }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "synapse.postgres.password" "initIfAbsent" false)) -}}
{{- with .value }}
  POSTGRES_PASSWORD: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "synapse.registrationSharedSecret" "initIfAbsent" true)) -}}
{{- with .registrationSharedSecret.value }}
  REGISTRATION_SHARED_SECRET: {{ . | b64enc }}
{{- end }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "synapse.signingKey" "initIfAbsent" true)) -}}
{{- with .signingKey.value }}
  SIGNING_KEY: {{ .| b64enc }}
{{- end }}
{{- end }}
{{- end }}
