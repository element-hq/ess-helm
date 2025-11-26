{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.deprecations" }}
{{- $root := .root }}
{{- $deprecations := list }}

{{- if gt (len $deprecations) 0 }}
DEPRECATIONS. Please read me and update
{{- printf "\n- %s" ($deprecations | join "\n- " ) }}
{{- end }}
{{- end }}
