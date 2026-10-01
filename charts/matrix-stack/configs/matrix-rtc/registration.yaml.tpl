{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}
{{- $root := .root -}}

id: matrix-rtc-authorisation-service
as_token: "${AS_TOKEN}"
hs_token: "${HS_TOKEN}"
sender_localpart: {{ $root.Values.matrixRTC.user.localpart }}
# The service asserts the identity of the local users it acts for (e.g. MSC4140 delayed leave events)
namespaces:
  users:
  - exclusive: false
    regex: "@.*:{{ tpl $root.Values.serverName $root }}"
# The service doesn't need any events pushed to it
url: null
# MSC4502: let the service check room memberships without joining the rooms
io.element.msc4502.scopes:
- "urn:matrix:client:io.element.msc4502:rooms:is_joined"
# MSC4512: Synapse proxies the rtc/livekit endpoints of the C-S and S-S APIs to the service
io.element.msc4512.proxy_prefix: rtc/livekit
io.element.msc4512.proxy_url: "http://{{ $root.Release.Name }}-matrix-rtc-authorisation-service.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:8080"
