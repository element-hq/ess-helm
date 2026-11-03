{{- /*
Copyright 2024 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.ingress.annotations" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.annotations missing context" .context -}}
{{- $annotations := .extraAnnotations | default dict -}}
{{- with required "element-io.ess-library.ingress.annotations context missing ingress" .ingress }}
{{- $tlsSecret := coalesce .tlsSecret $root.Values.ingress.tlsSecret -}}
{{- if and (not $tlsSecret) $root.Values.certManager -}}
{{- with $root.Values.certManager -}}
{{- with .clusterIssuer -}}
{{- $annotations = mustMergeOverwrite (dict "cert-manager.io/cluster-issuer" .) $annotations -}}
{{- end -}}
{{- with .issuer -}}
{{- $annotations = mustMergeOverwrite (dict "cert-manager.io/issuer" .) $annotations -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $annotations = mustMergeOverwrite $annotations ($root.Values.ingress.annotations | deepCopy) -}}
{{- $annotations = mustMergeOverwrite $annotations (.annotations | deepCopy) -}}
{{- with $annotations -}}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress-service.annotations" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress-service.annotations missing context" .context -}}
{{- $ingressService := .service -}}
{{- $annotations := .extraAnnotations | default dict -}}
{{- $annotations = mustMergeOverwrite $annotations ($root.Values.ingress.service.annotations | deepCopy) -}}
{{- if $ingressService.annotations }}
{{- $annotations = mustMergeOverwrite $annotations ($ingressService.annotations | deepCopy) -}}
{{- end -}}
{{- with $annotations -}}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}


{{- define "element-io.ess-library.ingress-service.spec" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress-service.spec missing context" .context -}}
{{- $headlessService := .headlessService | default false -}}
{{- $ingressService := .service -}}
{{ with $ingressService.type | default $root.Values.ingress.service.type }}
type: {{ . }}
{{ if and $headlessService (eq . "ClusterIP") }}
clusterIP: None
{{- end }}
{{- if (list "LoadBalancer" "NodePort") | has . }}
externalTrafficPolicy: {{ $ingressService.externalTrafficPolicy | default $root.Values.ingress.service.externalTrafficPolicy }}
{{- end }}
{{- end }}
{{- if hasKey $ingressService "externalIPs" }}
externalIPs: {{ $ingressService.externalIPs | toYaml | nindent 4 }}
{{- end }}
internalTrafficPolicy: {{ $ingressService.internalTrafficPolicy | default $root.Values.ingress.service.internalTrafficPolicy }}
ipFamilyPolicy: PreferDualStack
{{- end }}
{{- end }}

{{- define "element-io.ess-library.ingress.tls" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.tls missing context" .context -}}
{{- $ingress := required "element-io.ess-library.ingress.tls missing ingress" .ingress -}}
{{- $host := .host | default $ingress.host -}}
{{- $tlsEnabled := and $root.Values.ingress.tlsEnabled .ingress.tlsEnabled -}}
{{- $ingressName := required "element-io.ess-library.ingress.tls missing ingressName" .ingressName -}}
{{- if $tlsEnabled }}
tls:
{{- with (include "element-io.ess-library.ingress.tlsHostsSecret" (dict "root" $root "context" (dict "hosts" (list $host) "tlsSecret" $ingress.tlsSecret "ingressName" $ingressName))) }}
{{ . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.tlsHostsSecret" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.tlsHostsSecret missing context" .context -}}
{{- $ingressName := required "element-io.ess-library.ingress.tlsHostsSecret missing ingress name" .ingressName -}}
{{- $hosts := .hosts -}}
{{- $tlsSecret := coalesce .tlsSecret $root.Values.ingress.tlsSecret -}}
- hosts:
{{- range $host := $hosts }}
  - {{ (tpl $host $root) | quote }}
{{- end }}
{{ if or $tlsSecret $root.Values.certManager }}
  secretName: {{ (tpl ($tlsSecret | default (printf "{{ .Release.Name }}-%s-certmanager-tls" $ingressName))  $root) | quote }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.className" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress.className missing context" -}}
{{- end }}
{{- with coalesce .context $root.Values.ingress.className -}}
ingressClassName: {{ . | quote }}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress-controller-type" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress-controller-type missing context" -}}
{{- end -}}
{{- with coalesce .context $root.Values.ingress.controllerType -}}
{{- . -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.ingress-nginx-dot-path-type" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress.ingress-nginx-dot-path-type missing context" -}}
{{- end -}}
{{- if eq (include "element-io.ess-library.ingress-controller-type" (dict "root" $root "context" .context)) "ingress-nginx" -}}
ImplementationSpecific
{{- else -}}
Prefix
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.inboundTrafficHandler.ingress" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.ingress missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.ingress missing component" .component -}}
{{- $componentName := required "element-io.ess-library.inboundTrafficHandler.ingress missing componentName" .componentName -}}
{{- $ingressName := required "element-io.ess-library.inboundTrafficHandler.ingress missing ingressName" .ingressName -}}
{{- $labels := required "element-io.ess-library.inboundTrafficHandler.ingress missing labels" .labels -}}
{{- $rawHost := .host | default (dig "ingress" "host" "" $component) -}}
{{- $extraAnnotations := .extraAnnotations | default dict -}}
{{- $render := and $component.enabled (eq (include "element-io.ess-library.inboundTrafficHandler.isEnabled" (dict "root" $root "context" (dict "component" $component "trafficHandler" "ingress"))) "true") -}}
{{- if .requireHost -}}
{{- $render = and $render (include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" $component))) -}}
{{- end -}}
{{- if $render -}}
{{- $paths := include "element-io.ess-library.inboundTrafficHandler.publicPaths" (dict "root" $root "context" (dict "component" $component "componentName" $componentName)) | fromYamlArray }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
{{- include "element-io.ess-library.ingress.annotations" (dict "root" $root "context" (dict "ingress" $component.ingress "extraAnnotations" $extraAnnotations)) | nindent 2 }}
  labels:
    {{- $labels | nindent 4 }}
  name: {{ $root.Release.Name }}-{{ $ingressName }}
  namespace: {{ $root.Release.Namespace }}
spec:
{{- include "element-io.ess-library.ingress.tls" (dict "root" $root "context" (dict "ingress" $component.ingress "ingressName" $ingressName "host" $rawHost)) | nindent 2 }}
{{- include "element-io.ess-library.ingress.className" (dict "root" $root "context" $component.ingress.className) | nindent 2 }}
  rules:
  - host: {{ (tpl $rawHost $root) | quote }}
    http:
      paths:
{{- range $paths }}
      - path: {{ .path }}
        pathType: {{ if hasPrefix "/." .path }}{{ include "element-io.ess-library.ingress.ingress-nginx-dot-path-type" (dict "root" $root "context" $component.ingress.controllerType) | trim }}{{ else }}Prefix{{ end }}
        backend:
          service:
            name: {{ .serviceName | quote }}
            port:
{{- if .servicePortName }}
              name: {{ .servicePortName }}
{{- else }}
              number: {{ .servicePortNumber }}
{{- end }}
{{- end }}

{{- end -}}
{{- end -}}
{{- end -}}
