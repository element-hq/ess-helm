
{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}


{{- define "element-io.ess-library.postgres-host-port" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-host-port requires context" .context -}}
{{- if .postgres -}}
{{ (tpl .postgres.host $root) }}:{{ .postgres.port | default 5432 }}
{{- else if $root.Values.postgres.enabled -}}
{{ $root.Release.Name }}-postgres.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:5432
{{- else }}
{{- fail "You need to enable the chart Postgres or configure this component postgres" -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{- define "element-io.ess-library.postgres-env-var" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-env-var requires context" .context -}}
{{- printf "POSTGRES_%s_PASSWORD" (. | snakecase | upper) -}}
{{- end -}}
{{- end -}}
