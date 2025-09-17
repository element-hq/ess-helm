{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.element-admin.validations" }}
{{- $root := .root -}}
{{- with required "element-io.element-admin.validations missing context" .context -}}
{{ $messages := list }}
{{- if not .ingress.host -}}
{{ $messages = append $messages "elementAdmin.ingress.host is required when elementAdmin.enabled=true" }}
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

{{- define "element-io.element-admin.configmap-data" }}
{{- $root := .root }}
default.conf: |-
  {{- ($root.Files.Get "configs/element-admin/default.conf") | nindent 2 }}
# Customisations that we do at the http rather than the server level
http_customisations.conf: |-
  {{- ($root.Files.Get "configs/element-admin/http_customisations.conf") | nindent 2 }}
# For repeated inclusion in default.conf because the add_header directives need to be repeated as per
# https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header as they are only inherited from
# the server block iff there's no add_header directives in the location block
security_headers.conf: |-
  {{- ($root.Files.Get "configs/element-admin/security_headers.conf") | nindent 2 }}
{{- end }}

{{- define "element-io.element-admin.overrideEnv" -}}
{{- $root := .root -}}
{{- with required "element-io.element-admin.overrideEnv missing context" .context -}}
env:
- name: "SERVER_NAME"
  value: {{ (tpl $root.Values.serverName $root) | quote }}
{{- end -}}
{{- end -}}
