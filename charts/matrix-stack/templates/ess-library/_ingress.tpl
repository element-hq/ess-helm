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

{{- define "element-io.ess-library.ingress.tls.isEnabled" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.tls.isEnabled missing context" .context -}}
{{- and $root.Values.ingress.tlsEnabled .tlsEnabled -}}
{{- end -}}
{{- end -}}

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

{{- define "element-io.ess-library.ingress.parentRefs" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.parentRefs missing context" .context -}}
{{- $serviceName := required "element-io.ess-library.ingress.parentRefs missing serviceName" .serviceName -}}
{{- $globalHTTPRouteConfig := $root.Values.ingress.HTTPRoute | default dict -}}
{{- $httpRouteConfig := .HTTPRoute | default dict -}}
{{- $gateways := concat
    ($globalHTTPRouteConfig.existingGateways | default list)
    ($httpRouteConfig.existingGateways | default list)
-}}
{{- $builtinGateway := $root.Values.ingress.gateway | default dict -}}
{{- if or (gt (len $gateways) 0) $builtinGateway.create -}}
{{- if gt (len $gateways) 0 -}}
{{ toYaml $gateways }}
{{- end -}}
{{ if $builtinGateway.create }}
- name: {{ $root.Release.Name | quote }}
  namespace: {{ $root.Release.Namespace | quote }}
  kind: gateway
  group: gateway.networking.k8s.io
  sectionname: {{ printf "%s-%s" $root.Release.Name $serviceName | quote }}
{{ end }}
{{- else -}}
[]
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.isEnabled" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.isEnabled missing context" .context -}}
{{- $ingress := required "element-io.ess-library.ingress.isEnabled missing ingress" .ingress -}}
{{- $type := required "element-io.ess-library.ingress.isEnabled missing type" .type -}}
{{- $desiredType := coalesce $ingress.type $root.Values.ingress.type -}}
{{- $enabled := or $ingress.enabled $root.Values.ingress.enabled -}}
{{- and $enabled (eq $type $desiredType) -}}
{{- end -}}
{{- end -}}
