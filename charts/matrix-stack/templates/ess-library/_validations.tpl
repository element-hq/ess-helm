{{- /*
Copyright 2026 New Vector Ltd
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.validations.host" -}}
{{- $root := .root -}}
{{- $messages := list -}}
{{- with required "element-io.ess-library.validations.host missing context" .context -}}
{{- $componentName := required "element-io.ess-library.validations.host context is missing component" .component -}}
{{- $component := index $root.Values $componentName -}}
{{- with required "element-io.ess-library.validations.host invalid component" $component -}}
{{- $activeHandlerName := coalesce .inboundTrafficHandler $root.Values.inboundTrafficHandler -}}
{{- if not $activeHandlerName -}}
{{ $messages = append $messages (printf "inboundTrafficHandler or %s.inboundTrafficHandler is required when %s.enabled=true" $componentName $componentName) }}
{{- end }}
{{- $activeHandler := index . $activeHandlerName -}}
{{- if not $activeHandler.host -}}
{{ $messages = append $messages (printf "%s.%s.host is required when %s.enabled=true" $componentName $activeHandlerName $componentName) }}
{{- end }}
{{- end -}}
{{- end -}}
{{- toJson $messages -}}
{{- end -}}
