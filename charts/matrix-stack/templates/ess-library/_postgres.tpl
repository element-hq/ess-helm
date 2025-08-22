
{{- /*
Copyright 2025 New Vector Ltd

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
{{- $input := . -}}
{{- $output := list -}}
{{- range $input | splitList "" -}}
{{- if (. | regexMatch "[A-Z]") -}}
{{- $output = append $output "_" -}}
{{- end -}}
{{- $output = append $output . -}}
{{- end -}}
{{- printf "POSTGRES_%s_PASSWORD" (upper ($output | join "")) -}}
{{- end -}}
{{- end -}}
