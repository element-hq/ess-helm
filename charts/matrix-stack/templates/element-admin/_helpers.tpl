{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.element-admin.validations" }}
{{- $root := .root -}}
{{- with required "element-io.element-admin.validations missing context" .context -}}
{{ $messages := list }}
{{- with include "element-io.ess-library.inboundTrafficHandler.validateHost" (dict "root" $root "context" (dict "component" . "componentName" "elementAdmin")) }}
{{ $messages = append $messages . }}
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

{{- define "element-io.element-admin.inboundTrafficHandler.paths" -}}
{{- $root := .root -}}
{{- with required "element-io.element-admin.inboundTrafficHandler.paths missing context" .context -}}
- path: /
  serviceName: {{ $root.Release.Name }}-element-admin
  servicePortName: http
  servicePortNumber: 8080
{{- end -}}
{{- end -}}
