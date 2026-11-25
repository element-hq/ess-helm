{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.deprecations" }}
{{- $root := .root }}
{{- $deprecations := list }}

{{- with $root.Values.hookshot.redis }}
{{ $deprecations = append $deprecations "hookshot.redis is deprecated in favour of hookshot.redisOrValkey. All user values should be moved across" -}}
{{- end }}

{{- with $root.Values.matrixRTC.sfu.redis }}
{{ $deprecations = append $deprecations "matrixRTC.sfu.redis is deprecated in favour of matrixRTC.sfu.redisOrValkey. All user values should be moved across" -}}
{{- end }}

{{- with $root.Values.synapse.redis }}
{{ $deprecations = append $deprecations "synapse.redis is deprecated in favour of synapse.redisOrValkey. All user values should be moved across" -}}
{{- end }}

{{- if not $root.Values.matrixRTC.restrictRoomCreationToLocalUsers }}
{{ $deprecations = append $deprecations "matrixRTC.restrictRoomCreationToLocalUsers will be removed when MatrixRTC authoriser removes the legacy endpoints." -}}
{{- end }}

{{- with $root.Values.ingress.service }}
{{ $deprecations = append $deprecations "ingress.service is deprecated in favour of httpService. All user values should be moved to httpService" -}}
{{- end }}

{{- range $componentName := list "elementAdmin" "elementWeb" "hookshot" "matrixAuthenticationService" "matrixRTC" "synapse" "wellKnownDelegation" }}
{{- with (index $root.Values $componentName).ingress }}
{{- with .service }}
{{ $deprecations = append $deprecations (printf "%s.ingress.service is deprecated in favour of %s.httpService. All user values should be moved across" $componentName $componentName) -}}
{{- end }}
{{- end }}
{{- end }}

{{- if gt (len $deprecations) 0 }}
DEPRECATIONS. Please read me and update
{{- printf "\n- %s" ($deprecations | join "\n- " ) }}
{{- end }}
{{- end }}
