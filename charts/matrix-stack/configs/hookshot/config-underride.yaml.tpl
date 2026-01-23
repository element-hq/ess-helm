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

{{- end -}}
