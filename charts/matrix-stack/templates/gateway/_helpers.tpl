{{- /*
Copyright 2026 New Vector Ltd
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}
{{- define "element-io.gateway.tlsConfig" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.tlsConfig missing context" .context -}}
{{- $tlsSecret := coalesce
    .tlsSecret
    $root.Values.ingress.tlsSecret
    (printf "%s-%s-certmanager-tls" $root.Release.Name .name)
-}}
tls:
  certificateRefs:
    - group: ""
      kind: Secret
      name: {{ $tlsSecret | quote }}
  mode: Terminate
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.listeners" -}}
{{- $root := .root -}}
{{- $contexts := dict
    "element-admin" $root.Values.elementAdmin
    "element-web" $root.Values.elementWeb
    "hookshot" $root.Values.hookshot
    "matrix-authentication-service" $root.Values.matrixAuthenticationService
    "matrix-rtc" $root.Values.matrixRTC
    "synapse" $root.Values.synapse
    "well-known" $root.Values.wellKnownDelegation
-}}
{{- $listenFor := $root.Values.ingress.gateway.listenFor | default (list
    "element-admin"
    "element-web"
    "matrix-authentication-service"
    "matrix-rtc"
    "synapse"
    "well-known")
-}}
{{- if and (not $root.Values.ingress.gateway.listenFor) $root.Values.hookshot.enabled -}}
{{- $listenFor = append $listenFor "hookshot" -}}
{{- end -}}
{{- range $listenFor -}}
{{- $service := . -}}
{{- with required "element-io.gateway.listener missing context" (index $contexts $service) -}}
{{- if eq (include "element-io.ess-library.ingress.isEnabled" (dict "root" $root "context" (dict "ingress" .ingress "type" "HTTPRoute"))) "true" }}
- hostname: {{ .routes.host | default $root.Values.serverName | quote }}
  {{- if eq (include "element-io.ess-library.ingress.tls.isEnabled" (dict "root" $root "context" .ingress)) "true" }}
  port: 443
  protocol: HTTPS
  {{- include "element-io.gateway.tlsConfig" (dict "root" $root "context" (dict "tlsSecret" .ingress.tlsSecret "name" $service)) | nindent 2 }}
  {{- else }}
  port: 80
  protocol: HTTP
  {{- end }}
  name: {{ printf "%s-%s" $root.Release.Name $service | quote }}
  allowedRoutes:
    namespaces:
      from: Same
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.labels missing context" .context -}}
{{- $labels := .labels | default dict -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" $labels)) }}
app.kubernetes.io/component: matrix-stack-ingress
app.kubernetes.io/name: {{ $root.Release.Name }}
app.kubernetes.io/instance: {{ $root.Release.Name }}-gateway
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Chart.Version }}
{{- end -}}
{{- end -}}
