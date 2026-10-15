{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.service.ip-families" -}}
{{- $ipFamily := . -}}
{{- if eq $ipFamily "dual-stack" -}}
ipFamilyPolicy: PreferDualStack
ipFamilies:
  - IPv4
  - IPv6
{{- else if eq $ipFamily "ipv6" -}}
ipFamilyPolicy: SingleStack
ipFamilies:
  - IPv6
{{- else -}}
ipFamilyPolicy: SingleStack
ipFamilies:
  - IPv4
{{- end -}}
{{- end -}}
