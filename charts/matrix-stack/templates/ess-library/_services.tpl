{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.exposed-service.spec" -}}
{{- $root := .root -}}
{{- $exposedService := .exposedService -}}
type: {{ $exposedService.portType }}
{{- if hasKey $exposedService "externalIPs" }}
externalIPs: {{ $exposedService.externalIPs | toYaml | nindent 2 }}
{{- end }}
ipFamilyPolicy: {{ $exposedService.ipFamilyPolicy | default ((eq $root.Values.networking.ipFamily "dual-stack") | ternary "PreferDualStack" "SingleStack") }}
{{- with $exposedService.ipFamilies }}
ipFamilies:
  {{- toYaml . | nindent 2 }}
{{- end }}
internalTrafficPolicy: {{ $exposedService.internalTrafficPolicy }}
{{- if ne $exposedService.portType "ClusterIP" }}
externalTrafficPolicy: {{ $exposedService.externalTrafficPolicy }}
{{- end }}
{{- end -}}

{{- define "element-io.ess-library.http-service.spec" -}}
{{- $root := .root -}}
{{- $context := required "element-io.ess-library.http-service.spec missing context" .context -}}
{{- $httpService := $context.httpService | default dict -}}
{{- $legacyService := dict -}}
{{- if $context.ingress -}}
{{- $legacyService = $context.ingress.service | default dict -}}
{{- end -}}
{{- $globalIngressService := $root.Values.ingress.service | default dict -}}
{{- $globalHttpService := $root.Values.httpService | default dict -}}
{{- $type := coalesce $httpService.type $legacyService.type $globalIngressService.type $globalHttpService.type -}}
{{- $internalTrafficPolicy := coalesce $httpService.internalTrafficPolicy $legacyService.internalTrafficPolicy $globalIngressService.internalTrafficPolicy $globalHttpService.internalTrafficPolicy -}}
{{- $externalTrafficPolicy := "" -}}
{{- $emitExternalTrafficPolicy := false -}}
{{- $externalIPs := list -}}
{{- $emitExternalIPs := false -}}
{{- $clusterIP := "" -}}
{{- if and ($context.headlessService | default false) (eq $type "ClusterIP") -}}
{{- $clusterIP = "None" -}}
{{- end -}}
{{- if list "LoadBalancer" "NodePort" | has $type -}}
{{- $externalTrafficPolicy = coalesce $httpService.externalTrafficPolicy $legacyService.externalTrafficPolicy $globalIngressService.externalTrafficPolicy $globalHttpService.externalTrafficPolicy -}}
{{- $emitExternalTrafficPolicy = true -}}
{{- end -}}
{{- range $source := list $globalHttpService $globalIngressService $legacyService $httpService -}}
{{- if hasKey $source "externalIPs" -}}
{{- $externalIPs = $source.externalIPs -}}
{{- $emitExternalIPs = true -}}
{{- end -}}
{{- end -}}
type: {{ $type }}
{{- if $clusterIP }}
clusterIP: {{ $clusterIP }}
{{- end }}
{{- if $emitExternalTrafficPolicy }}
externalTrafficPolicy: {{ $externalTrafficPolicy }}
{{- end }}
{{- if $emitExternalIPs }}
externalIPs: {{ $externalIPs | toYaml | nindent 2 }}
{{- end }}
ipFamilyPolicy: PreferDualStack
internalTrafficPolicy: {{ $internalTrafficPolicy }}
{{- end -}}

{{- define "element-io.ess-library.http-service.annotations" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.http-service.annotations missing context" .context -}}
{{- $httpService := .httpService | default dict -}}
{{- $legacyService := dict -}}
{{- with .ingress -}}
{{- $legacyService = .service | default dict -}}
{{- end -}}
{{- $globalIngressService := $root.Values.ingress.service | default dict -}}
{{- $globalHttpService := $root.Values.httpService | default dict -}}
{{- $annotations := .extraAnnotations | default dict -}}
{{- range $source := list $globalHttpService $globalIngressService $legacyService $httpService -}}
{{- with $source.annotations -}}
{{- $annotations = mustMergeOverwrite $annotations (. | deepCopy) -}}
{{- end -}}
{{- end -}}
{{- with $annotations -}}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
