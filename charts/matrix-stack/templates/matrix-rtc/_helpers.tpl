{{- /*
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

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

{{- define "element-io.matrix-rtc-authorizer.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-rtc-authorizer
app.kubernetes.io/name: matrix-rtc-authorizer
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-authorizer
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-rtc-voip-server
app.kubernetes.io/name: matrix-rtc-sfu
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-sfu-rtc.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-rtc-voip-server
app.kubernetes.io/name: matrix-rtc-sfu-rtc
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-rtc-sfu-rtc
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-rtc-authorizer.env" }}
{{- $root := .root -}}
{{- with required "element-io.authorizer.env missing context" .context -}}
{{- $resultEnv := dict -}}
{{- range $envEntry := .extraEnv -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry.value -}}
{{- end -}}
{{- if (.livekitAuth).keysYaml }}
{{- $_ := set $resultEnv "LIVEKIT_KEY_FILE" (printf "/secrets/%s"
      (include "element-io.ess-library.provided-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitAuth.keysYaml"
              "defaultSecretName" (printf "%s-matrix-rtc-authorizer" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_KEYS_YAML"
              )
        ))) }}
{{- else }}
{{- $_ := set $resultEnv "LIVEKIT_KEY" ((.livekitAuth).key | default "matrix-rtc") -}}
{{- $_ := set $resultEnv "LIVEKIT_SECRET_FROM_FILE" (printf "/secrets/%s"
      (include "element-io.ess-library.init-secret-path" (
        dict "root" $root "context" (
          dict "secretPath" "matrixRTC.livekitAuth.secret"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_SECRET"
              "defaultSecretName" (printf "%s-matrix-rtc-authorizer" $root.Release.Name)
              "defaultSecretKey" "LIVEKIT_SECRET"
              )
        ))) }}
{{- end }}
{{- if .sfu.enabled -}}
{{- $_ := set $resultEnv "LIVEKIT_URL" (printf "wss://%s" (tpl .ingress.host $root)) -}}
{{- end -}}
{{- range $key, $value := $resultEnv }}
- name: {{ $key | quote }}
  value: {{ $value | quote }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.env" }}
{{- $root := .root -}}
{{- with required "element-io.authorizer missing context" .context -}}
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

{{- define "element-io.matrix-rtc-authorizer.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorizer.configSecrets missing context" .context -}}
{{- $configSecrets := list -}}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- if or ((.livekitAuth).keysYaml).value ((.livekitAuth).secret).value -}}
{{ $configSecrets = append $configSecrets (printf "%s-matrix-rtc-authorizer" $root.Release.Name) }}
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


{{- define "element-io.matrix-rtc-sfu.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.config missing context" .context -}}
{{- $config := (tpl ($root.Files.Get "configs/matrix-rtc/sfu/config.yaml.tpl") (dict "root" $root "context" .)) | fromYaml }}
config.yaml: |
{{- toYaml (mergeOverwrite $config (.additional | fromYaml)) | nindent 2 }}
{{- if not ($root.Values.matrixRTC.livekitAuth).keysYaml }}
keys-template.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/keys-template.yaml.tpl") dict) | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-authorizer.secret-data" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorizer secret missing context" .context -}}
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
