{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.service.ip-families" -}}
{{- $root := .root -}}
{{- $exposedService := .exposedService -}}
ipFamilyPolicy: {{ tpl $exposedService.ipFamilyPolicy $root }}
{{- with $exposedService.ipFamilies }}
ipFamilies:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
