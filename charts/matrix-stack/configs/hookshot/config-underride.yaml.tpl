{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root }}
{{- with required "hookshot/config-overrides.yaml.tpl missing context" .context }}
{{- $context := . -}}

widgets:
  roomSetupWidget:
    addOnInvite: true

permissions:
# Allow all users to send commands to existing services
- actor: {{ tpl $root.Values.serverName $root | quote }}
  services:
  - service: "*"
    level: manageConnections

{{- end -}}
