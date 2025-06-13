{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.pods.commonSpec" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.pods.commonSpec missing context" .context -}}
{{- $instanceSuffix := required "element-io.ess-library.pods.commonSpec missing context.instanceSuffix" .instanceSuffix -}}
{{- $serviceAccountNameSuffix := .serviceAccountNameSuffix | default .instanceSuffix -}}
{{- $usesMatrixTools := .usesMatrixTools | default false -}}
{{- $mountServiceAccountToken := .mountServiceAccountToken | default false -}}
{{- $deployment := required "element-io.ess-library.pods.commonSpec missing context.deployment" .deployment -}}
{{- with required "element-io.ess-library.pods.commonSpec missing context.componentValues" .componentValues -}}
{{- if and $deployment (gt (.replicas | int) 1) }}
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app.kubernetes.io/instance
            operator: In
            values:
            - "{{ $root.Release.Name }}-{{ $instanceSuffix }}"
        topologyKey: kubernetes.io/hostname
{{- end }}
automountServiceAccountToken: {{ $mountServiceAccountToken }}
serviceAccountName: {{ include "element-io.ess-library.serviceAccountName" (dict "root" $root "context" (dict "serviceAccount" .serviceAccount "nameSuffix" $serviceAccountNameSuffix)) }}
{{- include "element-io.ess-library.pods.pullSecrets" (dict "root" $root "context" (dict "pullSecrets" ((.image).pullSecrets | default list) "usesMatrixTools" $usesMatrixTools)) }}
{{- with .podSecurityContext }}
securityContext:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- include "element-io.ess-library.pods.tolerations" (dict "root" $root "context" .tolerations) }}
{{- include "element-io.ess-library.pods.topologySpreadConstraints" (dict "root" $root "context" (dict "instanceSuffix" $instanceSuffix "deployment" $deployment "topologySpreadConstraints" .topologySpreadConstraints)) }}
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.ess-library.pods.pullSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.pods.pullSecrets missing context" .context -}}
{{- $pullSecrets := list }}
{{- $pullSecrets = concat .pullSecrets $root.Values.imagePullSecrets }}
{{- if .usesMatrixTools -}}
{{- $pullSecrets = concat $pullSecrets $root.Values.matrixTools.image.pullSecrets }}
{{- end }}
{{- with ($pullSecrets | uniq) }}
imagePullSecrets:
{{ tpl (toYaml .) $root }}
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.ess-library.pods.tolerations" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.pods.tolerations missing context" -}}
{{- end }}
{{- $tolerations := concat .context $root.Values.tolerations }}
{{- with ($tolerations | uniq) }}
tolerations:
{{ toYaml . }}
{{- end }}
{{- end }}

{{- define "element-io.ess-library.pods.topologySpreadConstraints" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.pods.topologySpreadConstraints missing context" .context -}}
{{- $labelSelector := (dict "matchLabels" (dict "app.kubernetes.io/instance" (printf "%s-%s" $root.Release.Name .instanceSuffix))) }}
{{- $matchLabelKeys := .deployment | ternary (list "pod-template-hash") list }}
{{- $defaultConstraintSettings := dict "labelSelector" $labelSelector "matchLabelKeys" $matchLabelKeys "whenUnsatisfiable" "DoNotSchedule" }}
{{- $topologySpreadConstraints := list -}}
{{- range $constraint := coalesce .topologySpreadConstraints $root.Values.topologySpreadConstraints -}}
{{- $constraintWithDefault := (mustMergeOverwrite (deepCopy $defaultConstraintSettings) $constraint) -}}
{{- $defaultMatchLabels := $constraintWithDefault.labelSelector.matchLabels | deepCopy -}}
{{- range $key, $value := $constraintWithDefault.labelSelector.matchLabels -}}
{{- if eq $value nil -}}
{{- $defaultMatchLabels = (omit $defaultMatchLabels $key) -}}
{{- end -}}
{{- end -}}
{{- $_ := set $constraintWithDefault.labelSelector "matchLabels" $defaultMatchLabels -}}
{{- $topologySpreadConstraints = append $topologySpreadConstraints $constraintWithDefault -}}
{{- end }}
{{- with $topologySpreadConstraints }}
topologySpreadConstraints:
{{ toYaml . }}
{{- end }}
{{- end }}
{{- end }}

{{- /*
The only differences this has over (. | toYaml) are that
* it allows us to omit nullable values for individual properties
* it renders nothing rather than {} when no properties are specified.
*/ -}}
{{- define "element-io.ess-library.pods.probe" -}}
{{- with .failureThreshold }}
failureThreshold: {{ . }}
{{- end }}
{{- with .initialDelaySeconds }}
initialDelaySeconds: {{ . }}
{{- end }}
{{- with .periodSeconds }}
periodSeconds: {{ . }}
{{- end }}
{{- with .successThreshold }}
successThreshold: {{ . }}
{{- end }}
{{- with .timeoutSeconds }}
timeoutSeconds: {{ . }}
{{- end }}
{{- end }}

{{- define "element-io.ess-library.pods.env" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.pods.env missing context" .context -}}
{{- $componentValues := required "element-io.ess-library.pods.env missing context.componentValues" .componentValues -}}
{{- $resultEnv := dict -}}
{{- range $envEntry := $componentValues.extraEnv -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry -}}
{{- end -}}
{{- $componentName := required "element-io.ess-library.pods.env missing context.componentName" .componentName -}}
{{- $overrideEnvType := .overrideEnvSuffix | default "overrideEnv" -}}
{{- $overrideEnvDocument := include (printf "element-io.%s.%s" $componentName $overrideEnvType) (dict "root" $root "context" $componentValues) -}}
{{- $overrideEnvYaml := $overrideEnvDocument | fromYaml -}}
{{- range $envEntry := $overrideEnvYaml.env -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry -}}
{{- end -}}
{{- with $resultEnv }}
env:
{{- range $key, $fullEnvEntry := . }}
- {{ $fullEnvEntry | toYaml | indent 2 | trim }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
