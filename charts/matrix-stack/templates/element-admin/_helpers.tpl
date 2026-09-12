{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.element-admin.validations" }}
{{- $root := .root -}}
{{- with required "element-io.element-admin.validations missing context" .context -}}
{{ $messages := list }}
{{- $trafficHandler := include "element-io.ess-library.inboundTrafficHandler.name" (dict "root" $root "context" (dict "component" .)) -}}
{{- if and $trafficHandler (not (include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)))) -}}
{{ $messages = append $messages (printf "elementAdmin.%s.host is required when elementAdmin.enabled=true and inboundTrafficHandler is %s" $trafficHandler $trafficHandler) }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.element-admin.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.element-admin.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-admin-client
app.kubernetes.io/name: element-admin
app.kubernetes.io/instance: {{ $root.Release.Name }}-element-admin
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.element-admin.overrideEnv" -}}
{{- $root := .root -}}
{{- with required "element-io.element-admin.overrideEnv missing context" .context -}}
{{- if $root.Values.serverName }}
env:
- name: "SERVER_NAME"
  value: {{ (tpl $root.Values.serverName $root) | quote }}
{{- else -}}
env: []
{{- end -}}
{{- end -}}
{{- end -}}
