{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "configs/element-admin/http_customisations.conf.tpl missing context" .context -}}

server_tokens off;

{{- if has $root.Values.networking.ipFamily (list "ipv4" "dual-stack") }}
set_real_ip_from 0.0.0.0/0;
{{- end }}
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
set_real_ip_from ::/0;
{{- end }}
real_ip_header X-Forwarded-For;
{{- end }}
