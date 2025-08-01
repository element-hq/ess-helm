{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.haproxy.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.haproxy.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-stack-ingress
app.kubernetes.io/name: haproxy
app.kubernetes.io/instance: {{ $root.Release.Name }}-haproxy
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.haproxy.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.haproxy.configmap-data missing context" .context -}}
haproxy.cfg: |
{{- tpl ($root.Files.Get "configs/haproxy/haproxy.cfg.tpl") (dict "root" $root "context" .) | nindent 2 }}
{{- end -}}
{{- end -}}

{{- define "element-io.haproxy.overrideEnv" }}
env: []
{{- end -}}
