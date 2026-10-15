{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.service.spec" -}}
{{- $root := .root -}}
{{- $exposedService := .exposedService -}}
type: {{ $exposedService.portType }}
{{- if hasKey $exposedService "externalIPs" }}
externalIPs: {{ $exposedService.externalIPs | toYaml | nindent 2 }}
{{- end }}
ipFamilyPolicy: {{ $exposedService.ipFamilyPolicy | default ((eq $root.Values.networking.ipFamily "dual-stack") | ternary "PreferDualStack" "SingleStack") }}
{{- if hasKey $exposedService "ipFamilies" }}
ipFamilies:
  {{- toYaml $exposedService.ipFamilies | nindent 2 }}
{{- end }}
internalTrafficPolicy: {{ $exposedService.internalTrafficPolicy }}
{{- if ne $exposedService.portType "ClusterIP" }}
externalTrafficPolicy: {{ $exposedService.externalTrafficPolicy }}
{{- end }}
{{- end -}}
