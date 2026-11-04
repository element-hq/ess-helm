{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- /*
Listener sectionName for one hostname.
HTTPRoute parentRefs must use this same name.
*/ -}}
{{- define "element-io.gateway.listenerName" -}}
{{- with required "element-io.gateway.listenerName missing context" .context -}}
{{- $host := required "element-io.gateway.listenerName missing context.host" .host -}}
{{- $protocol := required "element-io.gateway.listenerName missing context.protocol" .protocol -}}
{{- $label := $host | lower | replace "*" "wildcard" | replace "_" "-" -}}
{{- printf "%s-%s" $protocol $label | trunc 253 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.name" -}}
{{- printf "%s-gateway" .root.Release.Name -}}
{{- end -}}

{{- define "element-io.gateway.tlsEnabled" -}}
{{- $gateway := .root.Values.gateway | default dict -}}
{{- if not (and (hasKey $gateway "tlsEnabled") (not $gateway.tlsEnabled)) -}}
true
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.redirectEnabled" -}}
{{- $root := .root -}}
{{- $gateway := $root.Values.gateway | default dict -}}
{{- if and (eq (include "element-io.gateway.tlsEnabled" (dict "root" $root)) "true") (not (and (hasKey $gateway "disableHTTPRedirect") $gateway.disableHTTPRedirect)) -}}
true
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.tlsSecretName" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.tlsSecretName missing context" .context -}}
{{- $host := required "element-io.gateway.tlsSecretName missing context.host" .host -}}
{{- $gateway := $root.Values.gateway | default dict -}}
{{- if $gateway.tlsSecret -}}
{{- tpl $gateway.tlsSecret $root -}}
{{- else -}}
{{- $label := $host | lower | replace "*" "wildcard" | replace "_" "-" | replace "." "-" -}}
{{- printf "%s-%s-tls" $root.Release.Name $label | trunc 253 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- /*
Hostnames that need a Gateway listener: enabled components whose handler is routes
and that have a host. Well-known uses serverName. Components that share a host share
one listener. Hookshot is included only when it has its own host.
*/ -}}
{{- define "element-io.gateway.hosts" -}}
{{- $root := .root -}}
{{- $hosts := dict -}}
{{- $components := list $root.Values.elementAdmin $root.Values.elementWeb $root.Values.hookshot $root.Values.matrixAuthenticationService $root.Values.matrixRTC $root.Values.synapse -}}
{{- range $component := $components -}}
{{- if $component -}}
{{- if and $component.enabled (eq (include "element-io.ess-library.inboundTrafficHandler.isEnabled" (dict "root" $root "context" (dict "component" $component "trafficHandler" "routes"))) "true") -}}
{{- $host := include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" $component)) | trim -}}
{{- if $host -}}
{{- $_ := set $hosts $host true -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- with $root.Values.wellKnownDelegation -}}
{{- if and .enabled (eq (include "element-io.ess-library.inboundTrafficHandler.isEnabled" (dict "root" $root "context" (dict "component" . "trafficHandler" "routes"))) "true") -}}
{{- $host := tpl ($root.Values.serverName | default "") $root | trim -}}
{{- if $host -}}
{{- $_ := set $hosts $host true -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- if $hosts -}}
{{- keys $hosts | sortAlpha | toYaml -}}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.listeners" -}}
{{- $root := .root -}}
{{- $rawHosts := include "element-io.gateway.hosts" (dict "root" $root) -}}
{{- $hosts := list -}}
{{- if $rawHosts -}}
{{- $hosts = $rawHosts | fromYamlArray -}}
{{- end -}}
{{- $tlsEnabled := eq (include "element-io.gateway.tlsEnabled" (dict "root" $root)) "true" -}}
{{- $redirectEnabled := eq (include "element-io.gateway.redirectEnabled" (dict "root" $root)) "true" -}}
{{- range $host := $hosts -}}
{{- if or (not $tlsEnabled) $redirectEnabled -}}
- name: {{ include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "host" $host "protocol" "http")) | quote }}
  hostname: {{ $host | quote }}
  port: 80
  protocol: HTTP
  allowedRoutes:
    namespaces:
      from: Same
{{ end -}}
{{- if $tlsEnabled -}}
- name: {{ include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "host" $host "protocol" "https")) | quote }}
  hostname: {{ $host | quote }}
  port: 443
  protocol: HTTPS
  tls:
    mode: Terminate
    certificateRefs:
    - group: ""
      kind: Secret
      name: {{ include "element-io.gateway.tlsSecretName" (dict "root" $root "context" (dict "host" $host)) | quote }}
  allowedRoutes:
    namespaces:
      from: Same
{{ end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.annotations" -}}
{{- $root := .root -}}
{{- $gateway := $root.Values.gateway | default dict -}}
{{- $annotations := dict -}}
{{- if not $gateway.tlsSecret -}}
{{- with $root.Values.certManager -}}
{{- with .clusterIssuer -}}
{{- $_ := set $annotations "cert-manager.io/cluster-issuer" . -}}
{{- end -}}
{{- with .issuer -}}
{{- $_ := set $annotations "cert-manager.io/issuer" . -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- with $gateway.annotations -}}
{{- $annotations = mustMergeOverwrite $annotations (. | deepCopy) -}}
{{- end -}}
{{- if gt (len $annotations) 0 -}}
annotations:
  {{- toYaml $annotations | nindent 2 }}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.gateway.labels missing context" .context -}}
{{- $labels := .labels | default dict -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" $labels)) }}
app.kubernetes.io/component: gateway
app.kubernetes.io/name: gateway
app.kubernetes.io/instance: {{ include "element-io.gateway.name" (dict "root" $root) }}
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Chart.Version }}
{{- end -}}
{{- end -}}

{{- define "element-io.gateway.redirectRoutes" -}}
{{- $root := .root -}}
{{- if eq (include "element-io.gateway.redirectEnabled" (dict "root" $root)) "true" -}}
{{- $rawHosts := include "element-io.gateway.hosts" (dict "root" $root) -}}
{{- $hosts := list -}}
{{- if $rawHosts -}}
{{- $hosts = $rawHosts | fromYamlArray -}}
{{- end -}}
{{- range $host := $hosts }}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  labels:
    {{- include "element-io.gateway.labels" (dict "root" $root "context" ($root.Values.gateway | default dict)) | trim | nindent 4 }}
  name: {{ printf "%s-redirect-%s" $root.Release.Name (sha256sum $host | trunc 10) }}
  namespace: {{ $root.Release.Namespace }}
spec:
  parentRefs:
  - name: {{ include "element-io.gateway.name" (dict "root" $root) | quote }}
    sectionName: {{ include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "host" $host "protocol" "http")) | quote }}
  hostnames:
  - {{ $host | quote }}
  rules:
  - filters:
    - type: RequestRedirect
      requestRedirect:
        scheme: https
        statusCode: 301
{{- end }}
{{- end -}}
{{- end -}}
