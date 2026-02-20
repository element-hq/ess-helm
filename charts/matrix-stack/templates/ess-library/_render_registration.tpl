{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.render-registration-container" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-registration-container missing context" .context -}}
{{- $context := . -}}
{{- $nameSuffix := required "element-io.ess-library.render-registration-container missing context.nameSuffix" .nameSuffix -}}
{{- $containerName := required "element-io.ess-library.render-registration-container missing context.containerName" .containerName -}}
{{- $isHook := .isHook -}}
{{- $extraVolumeMounts := .extraVolumeMounts -}}
{{- $templatesVolume := (.templatesVolume | default "plain-config") -}}
{{- $outputFile := required "element-io.ess-library.render-registration-container missing context.outputFile" .outputFile -}}
{{- $registrationTemplate := required "element-io.ess-library.render-registration-container missing context.registrationTemplate" .registrationTemplate -}}
- name: {{ $containerName }}
  {{- include "element-io.ess-library.pods.image" (dict "root" $root "context" $root.Values.matrixTools.image) | nindent 2 }}
{{- with .containersSecurityContext }}
  securityContext:
    {{- toYaml . | nindent 4 }}
{{- end }}
  args:
  - render-config
  - -output
  - /conf/{{ $outputFile }}
  - /config-templates/{{ $registrationTemplate }}
  {{ include "element-io.ess-library.pods.env" (dict "root" $root "context" (dict "componentValues" . "componentName" $nameSuffix
                                                    "overrideEnvSuffix" "renderRegistrationOverrideEnv" "isHook" $isHook)) | nindent 2 }}
{{- with .resources }}
  resources:
    {{- toYaml . | nindent 4 }}
{{- end }}
  volumeMounts:
{{- range $secret := include (printf "element-io.%s.registrationConfigSecrets" $nameSuffix) (dict "root" $root "context" .) | fromJsonArray }}
{{- with (tpl $secret $root) }}
  - mountPath: /secrets/{{ . }}
    name: "secret-{{ . | sha256sum | trunc 12 }}"
    readOnly: true
{{- end }}
{{- end }}
  - mountPath: /config-templates/{{ $registrationTemplate }}
    name: {{ $templatesVolume }}
    readOnly: true
    subPath: "{{ $registrationTemplate }}"
  - mountPath: /conf
    name: rendered-registration
    readOnly: false
{{- range $extraVolumeMounts }}
{{- if or (and $isHook ((list "hook" "both") | has (.mountContext | default "both")))
          (and (not $isHook) ((list "runtime" "both") | has (.mountContext | default "both"))) -}}
{{- $extraVolumeMount := . | deepCopy -}}
{{- $_ := unset $extraVolumeMount "mountContext" }}
  - {{- ($extraVolumeMount | toYaml) | nindent 4 }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end }}


{{- define "element-io.ess-library.render-registration-volumes" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-registration-volumes missing context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.render-registration-volumes missing context.nameSuffix" .nameSuffix -}}
- configMap:
    defaultMode: 420
    name: {{ include (printf "element-io.%s.configmap-name" $nameSuffix) (dict "root" $root "context" .) }}
  name: registration-templates
- emptyDir:
    medium: Memory
  name: "rendered-registration"
{{- end -}}
{{- end }}


{{- define "element-io.ess-library.render-registration-volume-mounts" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.render-registration-volume-mounts context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.render-registration-volume-mounts context.nameSuffix" .nameSuffix -}}
{{- $outputFile := required "element-io.ess-library.render-registration-volume-mounts context.outputFile" .outputFile -}}
- mountPath: "/conf/{{ $outputFile }}"
  name: rendered-registration
  subPath: {{ $outputFile }}
  readOnly: true
{{- end -}}
{{- end }}