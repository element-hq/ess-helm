{{- /*
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.matrix-rtc-sfu-jwt.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" .labels) }}
app.kubernetes.io/component: matrix-stack-sfu-jwt
app.kubernetes.io/name: matrix-rtc-sfu-jwt
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu-jwt
app.kubernetes.io/version: {{ .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" .labels) }}
app.kubernetes.io/component: matrix-stack-rtc
app.kubernetes.io/name: matrix-rtc-sfu
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu
app.kubernetes.io/version: {{ .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu-rtc.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" .labels) }}
app.kubernetes.io/component: matrix-stack-rtc
app.kubernetes.io/name: matrix-rtc-sfu-rtc
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu-rtc
app.kubernetes.io/version: {{ .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu-jwt.env" }}
{{- $root := .root -}}
{{- with required "element-io.sfu-jwt.env missing context" .context -}}
{{- $resultEnv := dict -}}
{{- range $envEntry := .extraEnv -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry.value -}}
{{- end -}}
{{- $_ := set $resultEnv "LIVEKIT_KEY_FROM_FILE" (printf "/secrets/%s"
      (include "element-io.ess-library.init-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitKey"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_KEY"
              "defaultSecretName" (printf "%s-matrix-rtc-sfu-jwt" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_KEY"
          )
      ))) }}
{{- $_ := set $resultEnv "LIVEKIT_SECRET_FROM_FILE" (printf "/secrets/%s"
      (include "element-io.ess-library.init-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitSecret"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_SECRET"
              "defaultSecretName" (printf "%s-matrix-rtc-sfu-jwt" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_SECRET"
              )
        ))) }}
{{- $_ := set $resultEnv "LIVEKIT_URL" (printf "wss://%s" (tpl .ingress.host $root)) -}}
{{- range $key, $value := $resultEnv }}
- name: {{ $key | quote }}
  value: {{ $value | quote }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.env" }}
{{- $root := .root -}}
{{- with required "element-io.sfu-jwt missing context" .context -}}
{{- $resultEnv := dict -}}
{{- range $envEntry := .extraEnv -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry.value -}}
{{- end -}}
{{- range $key, $value := $resultEnv }}
- name: {{ $key | quote }}
  value: {{ $value | quote }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu-jwt.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu-jwt.configSecrets missing context" .context -}}
{{- $configSecrets := list -}}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- if or .livekitKey.value .livekitSecret.value -}}
{{ $configSecrets = append $configSecrets (printf "%s-matrix-rtc-sfu-jwt" $root.Release.Name) }}
{{- end -}}
{{- with .livekitKey.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .livekitSecret.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}
