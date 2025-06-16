{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.element-web.validations" }}
{{- $root := .root -}}
{{- with required "element-io.element-web.validations missing context" .context -}}
{{ $messages := list }}
{{- if not .ingress.host -}}
{{ $messages = append $messages "elementWeb.ingress.host is required when elementWeb.enabled=true" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.element-web.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.element-web.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-client
app.kubernetes.io/name: element-web
app.kubernetes.io/instance: {{ $root.Release.Name }}-element-web
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.element-web.overrideEnv" -}}
{{- $root := .root -}}
{{- with required "element-io.element-web.overrideEnv missing context" .context -}}
{{- /*
https://github.com/nginxinc/docker-nginx/blob/1.26.1/entrypoint/20-envsubst-on-templates.sh#L31-L45
If pods run with a GID of 0 this makes $output_dir to appear writable to sh, however
due to running with a read-only FS the actual writing later fails. We short circuit this by using an
invalid template directory and so templating as a whole is skipped by the script
*/ -}}
env:
- name: "NGINX_ENVSUBST_TEMPLATE_DIR"
  value: "/non-existant-so-that-this-works-with-read-only-root-filesystem"
{{- end -}}
{{- end -}}


{{- define "element-io.element-web.nginx-configmap-data" }}
{{- $root := .root }}
default.conf: |-
  {{- ($root.Files.Get "configs/element-web/default.conf") | nindent 2 }}
# Customisations that we do at the http rather than the server level
http_customisations.conf: |-
  {{- ($root.Files.Get "configs/element-web/http_customisations.conf") | nindent 2 }}
# For repeated inclusion in default.conf because the add_header directives need to be repeated as per
# https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header as they are only inherited from
# the server block iff there's no add_header directives in the location block
security_headers.conf: |-
  {{- ($root.Files.Get "configs/element-web/security_headers.conf") | nindent 2 }}
{{- end }}

{{- define "element-io.element-web.configmap-data" -}}
{{- $root := .root }}
{{- with required "element-io.element-web.configmap-data missing context" .context -}}
config.json: |-
{{- (tpl ($root.Files.Get "configs/element-web/config.json.tpl") (dict "root" $root "context" .)) | nindent 2 }}
{{- end }}
{{- end }}
