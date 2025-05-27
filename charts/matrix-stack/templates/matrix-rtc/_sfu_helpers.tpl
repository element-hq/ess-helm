{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

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

{{- define "element-io.matrix-rtc-sfu.env" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-authorisation-service missing context" .context -}}
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

{{- define "element-io.matrix-rtc-sfu.matrixToolsEnv" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.matrixToolsEnv missing context" .context -}}
- name: "LIVEKIT_KEY"
  value: "{{ (.livekitAuth).key | default "matrix-rtc" }}"
- name: LIVEKIT_SECRET
  value: >-
    {{ (printf "{{ readfile \"/secrets/%s\" }}" (
        (include "element-io.ess-library.init-secret-path" (
            dict "root" $root
            "context" (dict
              "secretPath" "matrixRTC.livekitAuth.secret"
              "initSecretKey" "ELEMENT_CALL_LIVEKIT_SECRET"
              "defaultSecretName" (include "element-io.matrix-rtc-sfu.secret-name" (dict "root" $root))
              "defaultSecretKey" "LIVEKIT_SECRET"
              )
            )
          )
        )
      )
    }}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.configSecrets" -}}
{{- $root := .root -}}
{{- include "element-io.matrix-rtc-authorisation-service.configSecrets" (dict "root" $root "context" .) -}}
{{- end }}

{{- define "element-io.matrix-rtc-sfu.configmap-name" -}}
{{- $root := .root -}}
{{- $root.Release.Name }}-matrix-rtc-sfu
{{- end }}


{{- define "element-io.matrix-rtc-sfu.secret-name" }}
{{- $root := .root }}
{{- $root.Release.Name }}-matrix-rtc-authorisation-service
{{- end }}


{{- define "element-io.matrix-rtc-sfu.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.config missing context" .context -}}
{{- $config := (tpl ($root.Files.Get "configs/matrix-rtc/sfu/config.yaml.tpl") (dict "root" $root "context" .)) | fromYaml }}
config.yaml: |
{{- toYaml (mustMergeOverwrite $config (.additional | fromYaml)) | nindent 2 }}
{{- if not ($root.Values.matrixRTC.livekitAuth).keysYaml }}
keys-template.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/keys-template.yaml.tpl") dict) | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
