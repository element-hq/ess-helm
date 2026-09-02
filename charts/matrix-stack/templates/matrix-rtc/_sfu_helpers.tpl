{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.matrix-rtc-sfu.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
{{ $suffix := .suffix | default "" }}
app.kubernetes.io/component: matrix-rtc-voip-server
app.kubernetes.io/name: matrix-rtc-sfu{{ $suffix }}
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu{{ $suffix }}
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.renderConfigOverrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.renderConfigOverrideEnv missing context" .context -}}
env:
{{- if $root.Values.matrixRTC.sfu.manualIP }}
- name: NODE_IP
  value: "{{ $root.Values.matrixRTC.sfu.manualIP }}"
{{- else if not $root.Values.matrixRTC.sfu.useStunToDiscoverPublicIP }}
- name: NODE_IP
  valueFrom:
    fieldRef:
      fieldPath: status.{{ $root.Values.matrixRTC.sfu.nodeIPSource }}
{{- end }}
- name: LIVEKIT_SECRET
  value: >-
    {{ (printf "{{ readfile \"/secrets/%s\" }}" (
        (include "element-io.ess-library.init-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "matrixRTC.livekitAuth.secret"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_SECRET"
              "defaultSecretName" (printf "%s-matrix-rtc-authorisation-service" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_SECRET"
              )
            )
          )
        )
      )
    }}
{{- if $root.Values.matrixRTC.sfu.redisOrValkey }}
{{- if $root.Values.matrixRTC.sfu.redisOrValkey.password }}
- name: SFU_REDIS_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | quote }}"
        (
          include "element-io.ess-library.provided-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "matrixRTC.sfu.redisOrValkey.password"
              "defaultSecretName" (include "element-io.matrix-rtc-sfu.secret-name" (dict "root" $root "context" .))
              "defaultSecretKey" "REDIS_PASSWORD"
            )
          )
        )
    }}
{{- end }}
{{- else if $root.Values.matrixRTC.sfu.redis }}
{{- if $root.Values.matrixRTC.sfu.redis.password }}
- name: SFU_REDIS_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | quote }}"
        (
          include "element-io.ess-library.provided-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "matrixRTC.sfu.redis.password"
              "defaultSecretName" (include "element-io.matrix-rtc-sfu.secret-name" (dict "root" $root "context" .))
              "defaultSecretKey" "REDIS_PASSWORD"
            )
          )
        )
    }}
{{- end }}
{{- end }}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.configSecrets" -}}
{{- $root := .root -}}
{{- $configSecrets := list (include "element-io.matrix-rtc-sfu.secret-name" (dict "root" $root "context" .)) -}}
{{- with $root.Values.matrixRTC.sfu.additional -}}
{{- range $key := (. | keys | uniq | sortAlpha) -}}
{{- $prop := index $root.Values.matrixRTC.sfu.additional $key }}
{{- if $prop.configSecret }}
{{ $configSecrets = append $configSecrets (tpl $prop.configSecret $root) }}
{{- end }}
{{- end }}
{{- end }}
{{- with coalesce $root.Values.matrixRTC.sfu.redisOrValkey $root.Values.matrixRTC.sfu.redis }}
{{- if .password }}
{{- if .password.secret }}
{{ $configSecrets = append $configSecrets (tpl .password.secret $root) }}
{{- end }}
{{- end }}
{{- end }}
{{- $configSecrets := concat $configSecrets (include "element-io.matrix-rtc-authorisation-service.configSecrets" (dict "root" $root "context" .) | fromJsonArray) -}}
{{ $configSecrets | uniq | toJson }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu.configmap-name" -}}
{{- $root := .root -}}
{{- $root.Release.Name }}-matrix-rtc-sfu
{{- end }}


{{- define "element-io.matrix-rtc-sfu.secret-name" }}
{{- $root := .root }}
{{- $root.Release.Name }}-matrix-rtc-sfu
{{- end }}


{{- define "element-io.matrix-rtc-sfu.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.config missing context" .context -}}
config-underrides.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/config-underrides.yaml.tpl") (dict "root" $root "context" .)) | nindent 2 }}
config-overrides.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/config-overrides.yaml.tpl") (dict "root" $root "context" .)) | nindent 2 }}
keys-template.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/keys-template.yaml.tpl") (dict "root" $root)) | nindent 2 }}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.secret-data" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.secret-data" .context -}}
{{- with $root.Values.matrixRTC.sfu.additional }}
{{- range $key := (. | keys | uniq | sortAlpha) }}
{{- $prop := index $root.Values.matrixRTC.sfu.additional $key }}
{{- if $prop.config }}
user-{{ $key }}: {{ $prop.config | b64enc }}
{{- end }}
{{- end }}
{{- end }}
{{- if $root.Values.matrixRTC.sfu.redisOrValkey }}
{{- with $root.Values.matrixRTC.sfu.redisOrValkey.password }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixRTC.sfu.redisOrValkey.password" "initIfAbsent" false)) -}}
{{- with .value }}
REDIS_PASSWORD: {{ . | b64enc | quote }}
{{- end }}
{{- end }}
{{- else if $root.Values.matrixRTC.sfu.redis }}
{{- with $root.Values.matrixRTC.sfu.redis.password }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixRTC.sfu.redis.password" "initIfAbsent" false)) -}}
{{- with .value }}
REDIS_PASSWORD: {{ . | b64enc | quote }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
