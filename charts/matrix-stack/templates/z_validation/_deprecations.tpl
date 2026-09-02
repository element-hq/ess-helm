{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.deprecations" }}
{{- $root := .root }}
{{- $deprecations := list }}

{{- with $root.redis }}
{{ $deprecations = append $deprecations "redis is deprecated in favour of valkey. All user values should be moved to valkey" -}}
{{- end }}

{{- if gt (len $deprecations) 0 }}
DEPRECATIONS. Please read me and update
{{- printf "\n- %s" ($deprecations | join "\n- " ) }}
{{- end }}
{{- end }}
