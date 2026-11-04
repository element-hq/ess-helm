{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.httproute.annotations" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.httproute.annotations missing context" .context -}}
{{- $routes := required "element-io.ess-library.httproute.annotations context missing routes" .routes -}}
{{- $annotations := .extraAnnotations | default dict -}}
{{- $globalRoutes := $root.Values.routes | default dict -}}
{{- $annotations = mustMergeOverwrite $annotations (($globalRoutes.annotations | default dict) | deepCopy) -}}
{{- $annotations = mustMergeOverwrite $annotations (($routes.annotations | default dict) | deepCopy) -}}
{{- $cleaned := dict -}}
{{- range $key, $value := $annotations -}}
{{- if not (kindIs "invalid" $value) -}}
{{- $_ := set $cleaned $key $value -}}
{{- end -}}
{{- end -}}
{{- with $cleaned -}}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- /*
parentRefs come from the component routes, then the global routes.
When neither is set, gateway.create is true, and this route has a host, attach to the
generated Gateway listener for that host. sectionName matches element-io.gateway.listenerName.
*/ -}}
{{- define "element-io.ess-library.httproute.parentRefs" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.httproute.parentRefs missing context" .context -}}
{{- $routes := required "element-io.ess-library.httproute.parentRefs context missing routes" .routes -}}
{{- $host := .host | default "" -}}
{{- $globalRoutes := $root.Values.routes | default dict -}}
{{- $parentRefs := $routes.existingGateways | default $globalRoutes.existingGateways -}}
{{- if not $parentRefs -}}
{{- $gateway := $root.Values.gateway | default dict -}}
{{- if and $gateway.create $host -}}
{{- $protocol := "http" -}}
{{- if eq (include "element-io.gateway.tlsEnabled" (dict "root" $root)) "true" -}}
{{- $protocol = "https" -}}
{{- end -}}
{{- $sectionName := include "element-io.gateway.listenerName" (dict "root" $root "context" (dict "host" $host "protocol" $protocol)) -}}
{{- $parentRefs = list (dict "name" (include "element-io.gateway.name" (dict "root" $root)) "sectionName" $sectionName) -}}
{{- end -}}
{{- end -}}
{{- if $parentRefs -}}
parentRefs:
{{- range $parentRefs }}
- name: {{ required "HTTPRoute parentRef missing name" .name | quote }}
{{- with .namespace }}
  namespace: {{ . | quote }}
{{- end }}
{{- with .group }}
  group: {{ . | quote }}
{{- end }}
{{- with .kind }}
  kind: {{ . | quote }}
{{- end }}
{{- with .sectionName }}
  sectionName: {{ . | quote }}
{{- end }}
{{- with .port }}
  port: {{ . }}
{{- end }}
{{- end }}
{{- end }}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.inboundTrafficHandler.httproute" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.httproute missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.httproute missing component" .component -}}
{{- $componentName := required "element-io.ess-library.inboundTrafficHandler.httproute missing componentName" .componentName -}}
{{- $routeName := required "element-io.ess-library.inboundTrafficHandler.httproute missing routeName" .routeName -}}
{{- $labels := required "element-io.ess-library.inboundTrafficHandler.httproute missing labels" .labels -}}
{{- $rawHost := .host | default (dig "routes" "host" "" $component) -}}
{{- $renderedHost := "" -}}
{{- if $rawHost -}}
{{- $renderedHost = tpl $rawHost $root | trim -}}
{{- end -}}
{{- $extraAnnotations := .extraAnnotations | default dict -}}
{{- $render := and $component.enabled (eq (include "element-io.ess-library.inboundTrafficHandler.isEnabled" (dict "root" $root "context" (dict "component" $component "trafficHandler" "routes"))) "true") -}}
{{- if .requireHost -}}
{{- $render = and $render $renderedHost -}}
{{- end -}}
{{- if $render -}}
{{- $paths := include "element-io.ess-library.inboundTrafficHandler.publicPaths" (dict "root" $root "context" (dict "component" $component "componentName" $componentName)) | fromYamlArray }}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
{{- include "element-io.ess-library.httproute.annotations" (dict "root" $root "context" (dict "routes" ($component.routes | default dict) "extraAnnotations" $extraAnnotations)) | nindent 2 }}
  labels:
    {{- $labels | nindent 4 }}
  name: {{ $root.Release.Name }}-{{ $routeName }}
  namespace: {{ $root.Release.Namespace }}
spec:
{{- include "element-io.ess-library.httproute.parentRefs" (dict "root" $root "context" (dict "routes" ($component.routes | default dict) "host" $renderedHost)) | nindent 2 }}
{{- if $renderedHost }}
  hostnames:
  - {{ $renderedHost | quote }}
{{- end }}
  rules:
{{- range $paths }}
  - matches:
    - path:
        type: PathPrefix
        value: {{ .path | quote }}
    backendRefs:
    - name: {{ .serviceName | quote }}
      port: {{ required (printf "HTTPRoute path %s on %s requires servicePortNumber" .path $componentName) .servicePortNumber }}
{{- end }}

{{- end -}}
{{- end -}}
{{- end -}}
