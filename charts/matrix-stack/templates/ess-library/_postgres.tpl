
{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}


{{- define "element-io.ess-library.postgres-host-port" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-host-port requires context" .context -}}
{{- if .postgres -}}
{{- if kindIs "string" .postgres.host -}}
{{ (tpl .postgres.host $root) }}:{{ .postgres.port | default 5432 }}
{{- else if .postgres.host.value -}}
{{ .postgres.host.value }}:{{ .postgres.port | default 5432 }}
{{- else -}}
{{- fail "postgres-host-port: host is from a secret and cannot be resolved at Helm render time" -}}
{{- end -}}
{{- else if $root.Values.postgres.enabled -}}
{{ $root.Release.Name }}-postgres.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:5432
{{- else }}
{{- fail "You need to enable the chart Postgres or configure this component postgres" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- /* Returns just the host string (no port), for constructing addresses when port comes from a secret. */ -}}
{{- define "element-io.ess-library.postgres-host-value" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-host-value requires context" .context -}}
{{- if .postgres -}}
{{- if kindIs "string" .postgres.host -}}
{{ tpl .postgres.host $root }}
{{- else if .postgres.host.value -}}
{{ .postgres.host.value }}
{{- else -}}
{{- fail "postgres-host-value: host is from a secret and cannot be resolved at Helm render time" -}}
{{- end -}}
{{- else if $root.Values.postgres.enabled -}}
{{ $root.Release.Name }}-postgres.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}
{{- else }}
{{- fail "You need to enable the chart Postgres or configure this component postgres" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- /* Returns the direct value or ${ENV_VAR} for a postgres field that may be a plain string, integer, or credential object.
       Use in config file templates where the render-config tool will substitute ${ENV_VAR} at runtime. */ -}}
{{- define "element-io.ess-library.postgres-field-value" -}}
{{- $root := .root -}}
{{- $field := required "element-io.ess-library.postgres-field-value requires field" .field -}}
{{- $envVar := required "element-io.ess-library.postgres-field-value requires envVar" .envVar -}}
{{- if kindIs "string" $field -}}
{{ tpl $field $root }}
{{- else if or (kindIs "int" $field) (kindIs "int64" $field) (kindIs "float64" $field) -}}
{{ $field }}
{{- else if $field.value -}}
{{ $field.value }}
{{- else -}}
${{{ $envVar }}}
{{- end -}}
{{- end -}}


{{- define "element-io.ess-library.postgres-env-var" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-env-var requires context" .context -}}
{{- printf "POSTGRES_%s_PASSWORD" (. | snakecase | upper) -}}
{{- end -}}
{{- end -}}
