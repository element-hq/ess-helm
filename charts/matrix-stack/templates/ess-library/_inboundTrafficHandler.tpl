{{- /*
Copyright 2024 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.inboundTrafficHandler.host" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.host missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.host missing component" .component -}}
{{- $handler := coalesce $component.inboundTrafficHandler $root.Values.inboundTrafficHandler "none" -}}
{{- if eq $handler "ingress" -}}
{{- tpl (dig "ingress" "host" "" $component) $root -}}
{{- else if eq $handler "routes" -}}
{{- tpl (dig "routes" "host" "" $component) $root -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.inboundTrafficHandler.name" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.name missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.name missing component" .component -}}
{{- $handler := coalesce $component.inboundTrafficHandler $root.Values.inboundTrafficHandler "none" -}}
{{- if ne $handler "none" -}}
{{- $handler -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.httpRedirectRoute" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.httpRouteRedirect missing context" .context -}}
{{- $serviceName := required "element-io.ess-library.httpRedirectRoute context missing ServiceName" .serviceName -}}
{{- $component := required "element-io.ess-library.httpRedirectRoute context missing Component" .component -}}
{{- $host := required "element-io.ess-library.httpRedirectRoute context missing Host" .host -}}
{{- $labels := required "element-io.ess-library.httpRedirectRoute context missing Labels" .labels -}}
{{- $path := .path | default "/" -}}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
{{- include "element-io.ess-library.ingress.annotations" (dict "root" $root "context" (dict "ingress" $component.routes)) | nindent 2 }}
  labels:
    {{- $labels | nindent 4 }}
  name: {{ printf "%s-%s-redirect" $root.Release.Name $serviceName }}
  namespace: {{ $root.Release.Namespace }}
spec:
  parentRefs:
    {{- include "element-io.ess-library.ingress.parentRefs" (dict "root" $root "context" (dict "component" $component "serviceName" $serviceName "protocol" "http")) | nindent 4 }}
  hostnames:
    - {{ $host | quote }}
  rules:
    - matches:
      - path:
          type: PathPrefix
          value: {{ $path }}
      filters:
      - requestRedirect:
          scheme: https
          statusCode: 301
        type: RequestRedirect
{{- end -}}
{{- end -}}
