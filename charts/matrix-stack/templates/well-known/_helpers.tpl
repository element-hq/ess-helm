{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.well-known-delegation.validations" }}
{{ $root := .root }}
{{- with required "element-io.well-known-delegation.validations missing context" .context -}}
{{- $messages := list }}
{{- if not $root.Values.serverName -}}
{{ $messages = append $messages "serverName is required when wellKnownDelegation.enabled=true" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.well-known-delegation.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-delegation
app.kubernetes.io/name: well-known-delegation
app.kubernetes.io/instance: {{ $root.Release.Name }}-well-known-delegation
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Values.haproxy.image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.well-known-delegation-ingress.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation-ingress.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-stack-ingress
app.kubernetes.io/name: well-known-ingress
app.kubernetes.io/instance: {{ $root.Release.Name }}-well-known-ingress
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
k8s.element.io/target-name: haproxy
k8s.element.io/target-instance: {{ $root.Release.Name }}-haproxy
{{- end }}
{{- end }}


{{- define "element-io.well-known-delegation.client" }}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation.client missing context" .context -}}
{{- $config := dict -}}
{{- if $root.Values.synapse.enabled -}}
{{- with required "WellKnownDelegation requires synapse.ingress.host set" $root.Values.synapse.ingress.host -}}
{{- $mHomeserver := dict "base_url" (printf "https://%s" .) -}}
{{- $_ := set $config "m.homeserver" $mHomeserver -}}
{{- end -}}
{{- end -}}
{{- if include "element-io.matrix-authentication-service.readyToHandleAuth" (dict "root" $root) }}
{{- with required "WellKnownDelegation requires matrixAuthenticationService.ingress.host set" $root.Values.matrixAuthenticationService.ingress.host -}}
{{- $msc2965 := dict "issuer" (printf "https://%s/" .)
                     "account" (printf "https://%s/account" .)
-}}
{{- $_ := set $config "org.matrix.msc2965.authentication" $msc2965 -}}
{{- end -}}
{{- end -}}
{{- if $root.Values.matrixRTC.enabled -}}
{{- $_ := set $config "org.matrix.msc4143.rtc_foci" (list (dict "type" "livekit" "livekit_service_url" (printf "https://%s" $root.Values.matrixRTC.ingress.host))) -}}
{{- end -}}
{{- $additional := .additional.client | fromJson -}}
{{- tpl (toPrettyJson (mustMergeOverwrite $additional $config)) $root -}}
{{- end -}}
{{- end }}

{{- define "element-io.well-known-delegation.server" }}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation.server missing context" .context -}}
{{- $config := dict -}}
{{- if $root.Values.synapse.enabled -}}
{{- with required "WellKnownDelegation requires synapse.ingress.host set" $root.Values.synapse.ingress.host -}}
{{- $_ := set $config "m.server" (printf "%s:443" .) -}}
{{- end -}}
{{- end -}}
{{- $additional := .additional.server | fromJson -}}
{{- tpl (toPrettyJson (mustMergeOverwrite $additional $config)) $root -}}
{{- end -}}
{{- end }}

{{- define "element-io.well-known-delegation.support" }}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation.support missing context" .context -}}
{{- $config := dict -}}
{{- $additional := .additional.support | fromJson -}}
{{- tpl (toPrettyJson (mustMergeOverwrite $additional $config)) $root -}}
{{- end -}}
{{- end }}

{{- define "element-io.well-known-delegation.configmap-data" -}}
{{- $root := .root -}}
{{- with required "element-io.well-known-delegation.configmap-data missing context" .context -}}
client: |
  {{- (tpl (include "element-io.well-known-delegation.client" (dict "root" $root "context" .)) $root) | nindent 2 }}
server: |
  {{- (tpl (include "element-io.well-known-delegation.server" (dict "root" $root "context" .)) $root) | nindent 2 }}
support: |
  {{- (tpl (include "element-io.well-known-delegation.support" (dict "root" $root "context" .)) $root) | nindent 2 }}
{{- end -}}
{{- end -}}
