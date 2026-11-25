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
{{- with include "element-io.ess-library.inboundTrafficHandler.validateHost" (dict "root" $root "context" (dict "component" . "componentName" "hookshot" "when" "hookshot.enabled=true, synapse.enabled=false" "check" (not $root.Values.synapse.enabled))) }}
{{ $messages = append $messages . }}
{{- end }}
{{ $messages = concat $messages (include "element-io.ess-library.inline-additional-config-validation" (dict "root" $root "context" (dict "additional" .additional "path" "hookshot.additional")) | fromJsonArray) }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.hookshot.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-integrations
app.kubernetes.io/name: hookshot{{- (.appservice | default false) | ternary "-appservice" "" }}
app.kubernetes.io/instance: {{ $root.Release.Name }}-hookshot{{- (.appservice | default false) | ternary "-appservice" "" }}
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}


{{- define "element-io.hookshot.appservice-hash-label" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.appservice-hash-label requires context" .context -}}
{{- $destination := required "element-io.hookshot.appservice-hash-label context missing destination" .destination -}}
{{- include "element-io.ess-library.appservice-hash-label"
      (dict "root" $root "context" (dict "componentValues" $root.Values.hookshot
                                         "componentName" "hookshot"
                                         "templatePath" "configs/hookshot/registration.yaml.tpl"
                                         "destination" $destination)) -}}
{{- end -}}
{{- end -}}


{{- define "element-io.hookshot.configmap-name" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.configmap-name requires context" .context -}}
{{ $root.Release.Name }}-hookshot
{{- end -}}
{{- end }}


{{- define "element-io.hookshot.secret-name" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.secret-name requires context" .context -}}
{{- $isHook := .isHook }}
{{- if $isHook -}}
{{ $root.Release.Name }}-hookshot-pre
{{- else -}}
{{ $root.Release.Name }}-hookshot
{{- end }}
{{- end }}
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
  {{- if or .redisOrValkey .redis }}
  {{- with coalesce .redisOrValkey .redis }}
  {{- if .password }}
  {{- if .password.secret }}
  {{ $configSecrets = append $configSecrets (tpl .password.secret $root) }}
  {{- end }}
  {{- end }}
  {{- end }}
  {{- end }}
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
{{- if and $root.Values.hookshot.redisOrValkey $root.Values.hookshot.redisOrValkey.password }}
env:
- name: HOOKSHOT_REDIS_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | urlencode }}"
        (
          include "element-io.ess-library.provided-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "hookshot.redisOrValkey.password"
              "defaultSecretName" (include "element-io.hookshot.secret-name" (dict "root" $root "context" (dict "isHook" false)))
              "defaultSecretKey" "REDIS_PASSWORD"
            )
          )
        )
    }}
{{- else if and $root.Values.hookshot.redis $root.Values.hookshot.redis.password }}
env:
- name: HOOKSHOT_REDIS_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | urlencode }}"
        (
          include "element-io.ess-library.provided-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "hookshot.redis.password"
              "defaultSecretName" (include "element-io.hookshot.secret-name" (dict "root" $root "context" (dict "isHook" false)))
              "defaultSecretKey" "REDIS_PASSWORD"
            )
          )
        )
    }}
{{- else }}
env: []
{{- end }}
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
  {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "hookshot.passkey" "initIfAbsent" true)) -}}
  {{- with (.passkey).value }}
RSA_PASSKEY: {{ . | b64enc }}
  {{- end }}
  {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "hookshot.appserviceRegistration" "initIfAbsent" true)) -}}
  {{- with (.appserviceRegistration).value }}
REGISTRATION: {{ tpl . $root | b64enc }}
  {{- end }}
  {{- if .redisOrValkey }}
  {{- with .redisOrValkey.password }}
  {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "hookshot.redisOrValkey.password" "initIfAbsent" false)) -}}
  {{- with .value }}
REDIS_PASSWORD: {{ . | b64enc | quote }}
  {{- end }}
  {{- end }}
  {{- else if .redis }}
  {{- with .redis.password }}
  {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "hookshot.redis.password" "initIfAbsent" false)) -}}
  {{- with .value }}
REDIS_PASSWORD: {{ . | b64enc | quote }}
  {{- end }}
  {{- end }}
  {{- end }}
{{- include "element-io.ess-library.inline-additional-config-secret-entries" (dict "root" $root "context" (dict "additional" .additional)) }}
{{- end }}
{{- end -}}

{{- define "element-io.hookshot.inboundTrafficHandler.paths" -}}
{{- $root := .root -}}
{{- with required "element-io.hookshot.inboundTrafficHandler.paths missing context" .context -}}
- path: /widgetapi/v1
  serviceName: {{ $root.Release.Name }}-hookshot
  servicePortName: widgets
  servicePortNumber: 7778
- path: /
  serviceName: {{ $root.Release.Name }}-hookshot
  servicePortName: webhooks
  servicePortNumber: 7775
{{- end -}}
{{- end -}}

{{- define "element-io.hookshot.pvcName" -}}
{{- $root := .root -}}
{{- if $root.Values.hookshot.storage.existingClaim -}}
{{ tpl $root.Values.hookshot.storage.existingClaim $root }}
{{- else -}}
{{ $root.Release.Name }}-hookshot
{{- end -}}
{{- end }}
