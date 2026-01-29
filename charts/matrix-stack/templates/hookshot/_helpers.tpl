{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.hookshot.validations" }}
{{- $root := .root -}}
{{- with required "element-io.hookshot.validations missing context" .context -}}
{{ $messages := list }}
{{- if not $root.Values.serverName -}}
{{ $messages = append $messages "serverName is required when hookshot.enabled=true" }}
{{- end }}
{{- if and (not $root.Values.synapse.enabled) (not .ingress.host) -}}
{{ $messages = append $messages "hookshot.ingress.host is required when hookshot.enabled=true and synapse.enabled=false" }}
{{- end }}
{{- if and ($root.Values.matrixAuthenticationService.enabled) (.enableEncryption) -}}
{{ $messages = append $messages "hookshot.enableEncryption cannot be enabled when matrixAuthenticationService.enabled=true" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.hookshot.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-integrations
app.kubernetes.io/name: hookshot
app.kubernetes.io/instance: {{ $root.Release.Name }}-hookshot
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}


{{- define "element-io.hookshot.configmap-name" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.configmap-name requires context" .context -}}
{{ $root.Release.Name }}-hookshot
{{- end -}}
{{- end }}


{{- define "element-io.hookshot.secret-name" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.secret-name requires context" .context -}}
{{ $root.Release.Name }}-hookshot
{{- end -}}
{{- end }}


{{- define "element-io.hookshot.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.configSecrets missing context" .context -}}
{{ $configSecrets := list (printf "%s-hookshot" $root.Release.Name) }}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- with $root.Values.hookshot }}
  {{- with .appserviceRegistration -}}
    {{- if .value }}
      {{- $configSecrets = append $configSecrets (printf "%s-hookshot" $root.Release.Name) }}
    {{- else -}}
      {{- $configSecrets = append $configSecrets (tpl .secret $root) }}
    {{- end -}}
  {{- end -}}
  {{- with .passkey -}}
    {{- if .value }}
      {{- $configSecrets = append $configSecrets (printf "%s-hookshot" $root.Release.Name) }}
    {{- else -}}
      {{- $configSecrets = append $configSecrets (tpl .secret $root) }}
    {{- end -}}
  {{- end -}}
  {{- with .additional -}}
    {{- range $key := (. | keys | uniq | sortAlpha) -}}
      {{- $prop := index $root.Values.hookshot.additional $key }}
      {{- if $prop.configSecret }}
      {{ $configSecrets = append $configSecrets (tpl $prop.configSecret $root) }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}


{{- define "element-io.hookshot.overrideEnv" }}
{{- $root := .root -}}
env: []
{{- end -}}

{{- define "element-io.hookshot.renderConfigOverrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.hookshot.renderConfigOverrideEnv missing context" .context -}}
env: []
{{- end }}
{{- end }}

{{- define "element-io.hookshot.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.hookshot.configmap-data" .context -}}
config-underride.yaml: |
{{- (tpl ($root.Files.Get "configs/hookshot/config-underride.yaml.tpl") (dict "root" $root "context" .)) | nindent 2 }}
config-override.yaml: |
{{- (tpl ($root.Files.Get "configs/hookshot/config-override.yaml.tpl") (dict "root" $root "context" .)) | nindent 2 }}
{{- end -}}
{{- end -}}


{{- define "element-io.hookshot.secret-data" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.secret-data" .context -}}
  {{- with .passkey.value }}
RSA_PASSKEY: {{ . | b64enc }}
  {{- end }}
  {{- with .appserviceRegistration.value }}
REGISTRATION: {{ . | b64enc }}
  {{- end }}
  {{- with .additional }}
    {{- range $key := (. | keys | uniq | sortAlpha) }}
      {{- $prop := index $root.Values.hookshot.additional $key }}
      {{- if $prop.config }}
user-{{ $key }}: {{ (tpl $prop.config $root) | b64enc }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}
{{- end -}}

{{- define "element-io.hookshot.pvcName" -}}
{{- $root := .root -}}
{{- if $root.Values.hookshot.storage.existingClaim -}}
{{ tpl $root.Values.hookshot.storage.existingClaim $root }}
{{- else -}}
{{ $root.Release.Name }}-hookshot
{{- end -}}
{{- end }}
