{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.postgres.secret-name" }}
{{- $root := .root }}
{{- with required "element-io.postgres.secret-name requires context" .context }}
{{- $isHook := required "element-io.postgres.secret-name requires context.isHook" .isHook }}
{{- if $isHook }}
{{- $root.Release.Name }}-postgres-hook
{{- else }}
{{- $root.Release.Name }}-postgres
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.postgres.secret-data" }}
{{- $root := .root }}
{{- with required "element-io.postgres.secret-data requires context" .context }}
type: Opaque
data:
{{- with .adminPassword }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "postgres.adminPassword" "initIfAbsent" false)) }}
{{- with .value }}
  ADMIN_PASSWORD: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- range $key := (.essPasswords | keys | uniq | sortAlpha) }}
{{- if (index $root.Values $key).enabled }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" (printf "postgres.essPasswords.%s" $key) "initIfAbsent" true)) }}
{{- $prop := index $root.Values.postgres.essPasswords $key }}
{{- with $prop.value }}
  ESS_PASSWORD_{{ $key | upper }}: {{ .| b64enc }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
