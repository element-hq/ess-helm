{{- /*
Copyright 2026 New Vector Ltd
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}
{{- define "element-io.gateway.listenerName" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.listenerName missing context" .context -}}
{{- $serviceName := required "element-io.gateway.listenerName missing context.serviceName" .serviceName -}}
{{- $protocol := required "element-io.gateway.listenerName missing context.protocol" .protocol -}}
{{- printf "%s-%s-%s" $root.Release.Name $serviceName $protocol -}}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.tlsSecretName" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.tlsSecretName missing context" .context -}}
{{- $serviceName := required "element-io.gateway.listenerName missing context.serviceName" .serviceName -}}
{{- coalesce
    .tlsSecret
    (get (get $root.Values "routes" | default dict) "tlsSecret")
    (printf "%s-%s-certmanager-tls" $root.Release.Name $serviceName)
-}}
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
{{- $listenFor := $root.Values.gateway.listenFor | default (list
    "element-admin"
    "element-web"
    "matrix-authentication-service"
    "matrix-rtc"
    "synapse"
    "well-known")
-}}
{{- if and (not $root.Values.gateway.listenFor) $root.Values.hookshot.enabled -}}
{{- $listenFor = append $listenFor "hookshot" -}}
{{- end -}}
{{- $allowedRoutes := dict "namespaces" (dict "from" "Same") -}}
{{- $listeners := list -}}
{{- range $service := $listenFor -}}
{{- $component := required "element-io.gateway.listeners missing component context" (index $contexts $service) -}}
{{- if eq (include "element-io.ess-library.inboundTrafficHandler.isEnabled" (dict "root" $root "context" (dict "component" $component "trafficHandler" "routes"))) "true" -}}
{{- $host := $component.routes.host | default $root.Values.serverName -}}
{{- $listeners = append $listeners (dict
    "name" (include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "serviceName" $service "protocol" "http")))
    "hostname" $host
    "port" 80
    "protocol" "HTTP"
    "allowedRoutes" $allowedRoutes
) -}}
{{- if eq (include "element-io.ess-library.routes.tls.isEnabled" (dict "root" $root "context" $component.routes)) "true" -}}
{{- $tlsSecret := include "element-io.gateway.tlsSecretName" (dict "root" $root "context" (dict "serviceName" $service "tlsSecret" $component.routes.tlsSecret)) -}}
{{- $listeners = append $listeners (dict
    "name" (include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "serviceName" $service "protocol" "https")))
    "hostname" $host
    "port" 443
    "protocol" "HTTPS"
    "tls" (dict
        "mode" "Terminate"
        "certificateRefs" (list (dict "group" "" "kind" "Secret" "name" $tlsSecret))
    )
    "allowedRoutes" $allowedRoutes
) -}}

{{- end -}}
{{- end -}}
{{- end -}}
{{- toYaml $listeners }}
{{- end -}}

{{- define "element-io.gateway.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.labels missing context" .context -}}
{{- $labels := .labels | default dict -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" $labels)) }}
app.kubernetes.io/component: matrix-stack-ingress
app.kubernetes.io/name: gateway
app.kubernetes.io/instance: {{ $root.Release.Name }}-gateway
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Chart.Version }}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.name" -}}
{{ .root.Release.Name }}-gateway
{{- end -}}
