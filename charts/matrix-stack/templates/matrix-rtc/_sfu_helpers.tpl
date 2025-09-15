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

{{- define "element-io.matrix-rtc-sfu.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.matrix-rtc-sfu.renderConfigOverrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-rtc-sfu.renderConfigOverrideEnv missing context" .context -}}
env:
{{- with $root.Values.matrixRTC.sfu.manualIP }}
- name: NODE_IP
  value: "{{ . }}"
{{- end }}
{{- if and (not $root.Values.matrixRTC.sfu.useStunToDiscoverPublicIP) (not $root.Values.matrixRTC.sfu.manualIP) }}
- name: NODE_IP
  valueFrom:
    fieldRef:
      fieldPath: status.hostIP
{{- end }}
- name: "LIVEKIT_KEY"
  value: "{{ ($root.Values.matrixRTC.livekitAuth).key | default "matrix-rtc" }}"
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
{{- if not ($root.Values.matrixRTC.livekitAuth).keysYaml }}
keys-template.yaml: |
{{- (tpl ($root.Files.Get "configs/matrix-rtc/sfu/keys-template.yaml.tpl") dict) | nindent 2 }}
{{- end -}}
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
{{- end }}
{{- end }}
