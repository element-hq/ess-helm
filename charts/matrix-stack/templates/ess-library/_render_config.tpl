{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.render-config-container" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-config-container missing context" .context -}}
{{- $context := . -}}
{{- $nameSuffix := required "element-io.ess-library.render-config-container missing context.nameSuffix" .nameSuffix -}}
{{- $containerName := (.containerName | default "render-config") -}}
{{- $additionalPath := .additionalPath -}}
{{- $additionalProperty := dict -}}
{{- if $additionalPath }}
{{- $additionalProperty = include "element-io.ess-library.value-from-values-path" (dict "root" $root "context" $additionalPath) | fromJson -}}
{{- end -}}
{{- $outputFile := required "element-io.ess-library.render-config-container missing context.outputFile" .outputFile -}}
{{- $underrides := .underrides | default list -}}
{{- $overrides := required "element-io.ess-library.render-config-container missing context.overrides" .overrides -}}
- name: {{ $containerName }}
{{- with $root.Values.matrixTools.image -}}
{{- if .digest }}
  image: "{{ .registry }}/{{ .repository }}@{{ .digest }}"
  imagePullPolicy: {{ .pullPolicy | default "IfNotPresent" }}
{{- else }}
  image: "{{ .registry }}/{{ .repository }}:{{ .tag }}"
  imagePullPolicy: {{ .pullPolicy | default "Always" }}
{{- end }}
{{- end }}
{{- with .containersSecurityContext }}
  securityContext:
    {{- toYaml . | nindent 4 }}
{{- end }}
  command:
  - "/matrix-tools"
  - render-config
  - -output
  - /conf/{{ $outputFile }}
    {{- range $underrides }}
  - /config-templates/{{ . }}
    {{- end }}
    {{- range $key := ($additionalProperty | keys | uniq | sortAlpha) -}}
    {{- $prop := index $additionalProperty $key }}
    {{- if $prop.config }}
  - /secrets/{{ include (printf "element-io.%s.secret-name" $nameSuffix) (dict "root" $root "context" $context) }}/user-{{ $key }}
    {{- end }}
    {{- if $prop.configSecret }}
  - /secrets/{{ tpl $prop.configSecret $root }}/{{ $prop.configSecretKey }}
    {{- end }}
    {{- end }}
    {{- range $overrides }}
  - /config-templates/{{ . }}
    {{- end }}
  env:
  {{- include (printf "element-io.%s.matrixToolsEnv" $nameSuffix) (dict "root" $root "context" .) | nindent 2 }}
  {{- include (printf "element-io.%s.env" $nameSuffix) (dict "root" $root "context" .) | nindent 2 }}
{{- with .resources }}
  resources:
    {{- toYaml . | nindent 4 }}
{{- end }}
  volumeMounts:
  - mountPath: /config-templates
    name: plain-config
    readOnly: true
{{- range $secret := include (printf "element-io.%s.configSecrets" $nameSuffix) (dict "root" $root "context" .) | fromJsonArray }}
{{- with (tpl $secret $root) }}
  - mountPath: /secrets/{{ . }}
    name: "secret-{{ . | sha256sum | trunc 12 }}"
    readOnly: true
{{- end }}
{{- end }}
  - mountPath: /conf
    name: rendered-config
    readOnly: false
{{- end }}
{{- end }}


{{- define "element-io.ess-library.render-config-volumes" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-config-volumes missing context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.render-config-volumes missing context.nameSuffix" .nameSuffix -}}
- configMap:
    defaultMode: 420
    name: {{ include (printf "element-io.%s.configmap-name" $nameSuffix) (dict "root" $root "context" .) }}
  name: plain-config
{{- range $secret := include (printf "element-io.%s.configSecrets" $nameSuffix) (dict "root" $root "context" .) | fromJsonArray }}
{{- with (tpl $secret $root) }}
- secret:
    secretName: {{ . }}
  name: secret-{{ . | sha256sum | trunc 12  }}
{{- end }}
{{- end }}
- emptyDir:
    medium: Memory
  name: "rendered-config"
{{- end -}}
{{- end -}}


{{- define "element-io.ess-library.render-config-volume-mounts" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-config-volume-mounts context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.render-config-volume-mounts context.nameSuffix" .nameSuffix -}}
{{- $outputFile := required "element-io.ess-library.render-config-volume-mounts context.outputFile" .outputFile -}}
- mountPath: "/conf/{{ $outputFile }}"
  name: rendered-config
  subPath: {{ $outputFile }}
  readOnly: true
{{- range $secret := include (printf "element-io.%s.configSecrets" $nameSuffix) (dict "root" $root "context" .) | fromJsonArray }}
{{- with (tpl $secret $root) }}
- mountPath: /secrets/{{ . }}
  name: "secret-{{ . | sha256sum | trunc 12 }}"
  readOnly: true
{{- end }}
{{- end }}
{{- end -}}
{{- end -}}
