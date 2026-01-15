{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}
{{- $root := .root -}}

rate_limited: false
namespaces:
  users: ["@{{ $root.Values.hookshot.user.localpart }}:{{ $root.Values.servername }}"]
id: hookshot
as_token: "${AS_TOKEN}"
hs_token: "${HS_TOKEN}"
url: "http://{{ $root.Release.Name }}-hookshot:9993"
sender_localpart: {{ $root.Values.hookshot.user.localpart }}

org.matrix.msc3202: true
