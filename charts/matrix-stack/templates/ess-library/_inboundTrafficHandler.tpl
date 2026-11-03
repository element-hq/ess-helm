{{- /*
Copyright 2024 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.inboundTrafficHandler.isEnabled" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.isEnabled missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.isEnabled missing component" .component -}}
{{- $trafficHandler := required "element-io.ess-library.inboundTrafficHandler.isEnabled missing trafficHandler" .trafficHandler -}}
{{- $handler := $component.inboundTrafficHandler | default $root.Values.inboundTrafficHandler -}}
{{- if eq $handler $trafficHandler -}}
true
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.inboundTrafficHandler.host" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.host missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.host missing component" .component -}}
{{- tpl (dig "ingress" "host" "" $component) $root -}}
{{- end -}}
{{- end -}}

{{- /*
Returns an error message when an active inbound traffic handler has no host.
`when` replaces the "<component>.enabled=true" clause. `check` skips the requirement when false.
*/ -}}
{{- define "element-io.ess-library.inboundTrafficHandler.validateHost" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.validateHost missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.validateHost missing component" .component -}}
{{- $componentName := required "element-io.ess-library.inboundTrafficHandler.validateHost missing componentName" .componentName -}}
{{- $check := true -}}
{{- if hasKey . "check" -}}
{{- $check = .check -}}
{{- end -}}
{{- $handler := include "element-io.ess-library.inboundTrafficHandler.name" (dict "root" $root "context" (dict "component" $component)) -}}
{{- if and $check $handler (not (include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" $component)))) -}}
{{- $when := .when | default (printf "%s.enabled=true" $componentName) -}}
{{- printf "%s.%s.host is required when %s and inboundTrafficHandler is %s" $componentName $handler $when $handler -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.inboundTrafficHandler.name" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.name missing context" .context -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.name missing component" .component -}}
{{- $handler := $component.inboundTrafficHandler | default $root.Values.inboundTrafficHandler -}}
{{- if ne $handler "none" -}}
{{- $handler -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- /*
Component path helpers return a YAML list. Each item has:
  path, serviceName, servicePortName (Ingress), servicePortNumber (HTTPRoute)
'publicPaths' is what Ingress and HTTPRoute manifests expose.
*/ -}}
{{- define "element-io.ess-library.inboundTrafficHandler.publicPaths" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.inboundTrafficHandler.publicPaths missing context" .context -}}
{{- $componentName := required "element-io.ess-library.inboundTrafficHandler.publicPaths missing componentName" .componentName -}}
{{- $component := required "element-io.ess-library.inboundTrafficHandler.publicPaths missing component" .component -}}
{{- $paths := include (printf "element-io.%s.inboundTrafficHandler.paths" $componentName) (dict "root" $root "context" $component) | fromYamlArray -}}
{{- if eq $componentName "synapse" -}}
{{- $exposed := list -}}
{{- range $path := $paths -}}
{{- if eq $path.availability "catch_all" -}}
{{- $covered := false -}}
{{- range $other := $paths -}}
{{- if and (has $other.availability (list "only_externally" "blocked")) (hasPrefix $other.path $path.path) -}}
{{- $covered = true -}}
{{- end -}}
{{- end -}}
{{- if not $covered -}}
{{- $exposed = append $exposed $path -}}
{{- end -}}
{{- else if ne $path.availability "internally_and_externally" -}}
{{- $exposed = append $exposed $path -}}
{{- end -}}
{{- end -}}
{{- $paths = $exposed -}}
{{- end -}}
{{- $paths | toYaml -}}
{{- end -}}
{{- end -}}
