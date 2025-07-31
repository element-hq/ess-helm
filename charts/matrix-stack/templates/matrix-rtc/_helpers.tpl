{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.matrix-rtc.validations" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.validations missing context" .context -}}
{{ $messages := list }}
{{- if not .ingress.host -}}
{{ $messages = append $messages "matrixRTC.ingress.host is required when matrixRTC.enabled=true" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-ingress.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-rtc
app.kubernetes.io/name: matrix-rtc
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-authorisation-service.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-rtc-authorisation-service
app.kubernetes.io/name: matrix-rtc-authorisation-service
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-authorisation-service
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-rtc-authorisation-service.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorisation-service.overrideEnv missing context" .context -}}
env:
{{- if (.livekitAuth).keysYaml }}
- name: "LIVEKIT_KEY_FILE"
  value: {{ printf "/secrets/%s"
      (include "element-io.ess-library.provided-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitAuth.keysYaml"
              "defaultSecretName" (printf "%s-matrix-rtc-authorisation-service" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_KEYS_YAML"
              )
        )) }}
{{- else }}
- name: "LIVEKIT_KEY"
  value: {{ (.livekitAuth).key | default "matrix-rtc" }}
- name: "LIVEKIT_SECRET_FROM_FILE"
  value: {{ printf "/secrets/%s"
      (include "element-io.ess-library.init-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitAuth.secret"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_SECRET"
              "defaultSecretName" (printf "%s-matrix-rtc-authorisation-service" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_SECRET"
              )
        )) }}
{{- end }}
{{- if .sfu.enabled }}
- name: "LIVEKIT_URL"
  value: {{ printf "wss://%s" (tpl .ingress.host $root) }}
{{- end }}
- name: "LIVEKIT_FULL_ACCESS_HOMESERVERS"
{{- if $root.Values.serverName }}
  value: {{ (.restrictRoomCreationToLocalUsers | ternary (tpl $root.Values.serverName $root) "*") | quote }}
{{- else }}
  value: "*"
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-authorisation-service.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorisation-service.configSecrets missing context" .context -}}
{{- $configSecrets := list -}}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- with $root.Values.matrixRTC -}}
{{- if or ((.livekitAuth).keysYaml).value ((.livekitAuth).secret).value -}}
{{ $configSecrets = append $configSecrets (printf "%s-matrix-rtc-authorisation-service" $root.Release.Name) }}
{{- end -}}
{{- with ((.livekitAuth).keysYaml).secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with ((.livekitAuth).secret).secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-rtc-authorisation-service.secret-data" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorisation-service secret missing context" .context -}}
{{- if not .keysYaml }}
  {{- if $root.Values.matrixRTC.sfu.enabled -}}
    {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixRTC.livekitAuth.secret" "initIfAbsent" true)) }}
  {{- end }}
{{- else }}
  {{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixRTC.livekitAuth.keysYaml" "initIfAbsent" false)) }}
{{- end }}
{{- with .livekitAuth -}}
  {{- with .keysYaml }}
    {{- with .value }}
  LIVEKIT_KEYS_YAML: {{ . | b64enc }}
    {{- end -}}
  {{- end -}}
  {{- with .secret }}
    {{- with .value }}
  LIVEKIT_SECRET: {{ . | b64enc }}
    {{- end -}}
  {{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
