{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.synapse.validations" }}
{{ $root := .root }}
{{- with required "element-io.synapse.validations missing context" .context -}}
{{ $messages := list }}
{{- if not .ingress.host -}}
{{ $messages = append $messages "synapse.ingress.host is required when synapse.enabled=true" }}
{{- end }}
{{- if not $root.Values.serverName -}}
{{ $messages = append $messages "serverName is required when synapse.enabled=true" }}
{{- end }}
{{- if and (not $root.Values.postgres.enabled) (not .postgres) -}}
{{ $messages = append $messages "synapse.postgres is required when synapse.enabled=true but postgres.enabled=false" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-server
app.kubernetes.io/name: synapse
app.kubernetes.io/instance: {{ $root.Release.Name }}-synapse
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
k8s.element.io/synapse-instance: {{ $root.Release.Name }}-synapse
{{- end }}
{{- end }}

{{- define "element-io.synapse-check-config.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-server
app.kubernetes.io/name: synapse-check-config
app.kubernetes.io/instance: {{ $root.Release.Name }}-synapse-check-config
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Values.synapse.image.tag }}
k8s.element.io/synapse-instance: {{ $root.Release.Name }}-synapse-check-config
{{- end }}
{{- end }}

{{- define "element-io.synapse-ingress.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse-ingress.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels)) }}
app.kubernetes.io/component: matrix-stack-ingress
app.kubernetes.io/name: synapse
app.kubernetes.io/instance: {{ $root.Release.Name }}-synapse
k8s.element.io/target-name: haproxy
k8s.element.io/target-instance: {{ $root.Release.Name }}-haproxy
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.process.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-server
app.kubernetes.io/name: synapse-{{ .processType }}
app.kubernetes.io/instance: {{ $root.Release.Name }}-synapse-{{ .processType }}
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{ if required "element-io.synapse.process.labels missing context.isHook" .isHook }}
k8s.element.io/synapse-instance: {{ $root.Release.Name }}-synapse-check-config
{{ else }}
k8s.element.io/synapse-instance: {{ $root.Release.Name }}-synapse
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.synapse-redis.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse-redis.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-server-pubsub
app.kubernetes.io/name: synapse-redis
app.kubernetes.io/instance: {{ $root.Release.Name }}-synapse-redis
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.synapse-redis.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.synapse.enabledWorkers" -}}
{{- $root := .root -}}
{{ $enabledWorkers := dict }}
{{- range $workerType, $workerDetails := $root.Values.synapse.workers }}
{{- if $workerDetails.enabled }}
{{ $_ := set $enabledWorkers $workerType $workerDetails }}
{{- end }}
{{- end }}
{{ $enabledWorkers | toJson }}
{{- end }}

{{- define "element-io.synapse.pvcName" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.pvcName missing context" .context -}}
{{- if $root.Values.synapse.media.storage.existingClaim -}}
{{ tpl $root.Values.synapse.media.storage.existingClaim $root }}
{{- else -}}
{{ $root.Release.Name }}-synapse-media
{{- end -}}
{{- end }}
{{- end }}

{{- define "element-io.synapse-python.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.synapse-python.overrideEnv missing context" .context -}}
env:
- name: "LD_PRELOAD"
  value: "libjemalloc.so.2"
{{- end -}}
{{- end -}}

{{- define "element-io.synapse.ingress.additionalPaths" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.ingress.additionalPaths missing context" .context -}}
{{- if include "element-io.matrix-authentication-service.readyToHandleAuth" (dict "root" $root) }}
{{- range $apiVersion := list "api/v1" "r0" "v3" "unstable" }}
{{- range $apiSubpath := list "login" "refresh" "logout" }}
- path: "/_matrix/client/{{ $apiVersion }}/{{ $apiSubpath }}"
  availability: only_externally
  service:
    name: "{{ $root.Release.Name }}-matrix-authentication-service"
    port:
      name: http
{{- end }}
{{- end }}
{{- end }}
{{- range $root.Values.synapse.ingress.additionalPaths }}
- {{ . | toYaml | indent 2 | trim }}
{{- end -}}
{{- end -}}
{{- end -}}


{{- /* The filesystem structure is `/secrets`/<< secret name>>/<< secret key >>.
        The non-defaulted values are handling the case where the credential is provided by an existing Secret
        The default values are handling the case where the credential is provided plain in the Helm chart and we add it to our Secret with a well-known key.

        These could be done as env vars with valueFrom.secretKeyRef, but that triggers CKV_K8S_35.
        Environment variables values found in the config file as ${VARNAME} are parsed through go template engine before being replaced in the target file.
*/}}
{{- define "element-io.synapse.renderConfigOverrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.synapse.renderConfigOverrideEnv missing context" .context -}}
{{- $isHook := required "element-io.synapse.renderConfigOverrideEnv requires context.isHook" .isHook }}
env:
- name: SYNAPSE_POSTGRES_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | quote }}"
        (
          include "element-io.ess-library.postgres-secret-path" (
            dict "root" $root
            "context" (dict
              "essPassword" "synapse"
              "initSecretKey" "POSTGRES_SYNAPSE_PASSWORD"
              "componentPasswordPath" "synapse.postgres.password"
              "defaultSecretName" (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook)))
              "defaultSecretKey" "POSTGRES_PASSWORD"
              "isHook" $isHook
            )
          )
        )
    }}
- name: APPLICATION_NAME
  value: >-
    {{ printf "{{ hostname }}" }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.configmap-name" }}
{{- $root := .root }}
{{- with required "element-io.synapse.configmap-name requires context" .context }}
{{- $isHook := required "element-io.synapse.configmap-name requires context.isHook" .isHook }}
{{- if $isHook }}
{{- $root.Release.Name }}-synapse-hook
{{- else }}
{{- $root.Release.Name }}-synapse
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.configmap-data" }}
{{- $root := .root }}
{{- with required "element-io.synapse.configmap-data requires context" .context }}
{{- $isHook := required "element-io.synapse.configmap-data requires context.isHook" .isHook }}
01-homeserver-underrides.yaml: |
{{- (tpl ($root.Files.Get "configs/synapse/synapse-01-shared-underrides.yaml.tpl") (dict "root" $root)) | nindent 2 }}
{{- /*02 files are user provided in Helm values and end up in the Secret*/}}
{{- /*03 files are user provided as secrets rather than directly in Helm*/}}
04-homeserver-overrides.yaml: |
{{- (tpl ($root.Files.Get "configs/synapse/synapse-04-homeserver-overrides.yaml.tpl") (dict "root" $root "context" (mustMergeOverwrite ($root.Values.synapse | deepCopy) (dict "isHook" $isHook)))) | nindent 2 }}
05-main.yaml: |
{{- (tpl ($root.Files.Get "configs/synapse/synapse-05-process-specific.yaml.tpl") (dict "root" $root "context" (dict "processType" "main"))) | nindent 2 }}
{{- if not $isHook }}
{{- range $workerType, $workerDetails := (include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson }}
05-{{ $workerType }}.yaml: |
{{- (tpl ($root.Files.Get "configs/synapse/synapse-05-process-specific.yaml.tpl") (dict "root" $root "context" (dict "processType" $workerType))) | nindent 2 }}
{{- end }}
{{- end }}
log_config.yaml: |
{{- (tpl ($root.Files.Get "configs/synapse/synapse-log-config.yaml.tpl") (dict "root" $root)) | nindent 2 }}
{{- end }}
{{- end }}


{{- define "element-io.synapse-redis.configmap-data" -}}
{{- $root := .root -}}
redis.conf: |
{{- ($root.Files.Get "configs/synapse/redis.conf") | nindent 2 -}}
{{- end -}}


{{- define "element-io.synapse-haproxy.configmap-data" -}}
{{- $root := .root -}}
429.http: |
{{- (tpl ($root.Files.Get "configs/haproxy/429.http.tpl") dict) | nindent 2 }}
path_map_file: |
{{- (tpl ($root.Files.Get "configs/synapse/path_map_file.tpl") (dict "root" $root)) | nindent 2 }}
path_map_file_get: |
{{- (tpl ($root.Files.Get "configs/synapse/path_map_file_get.tpl") (dict "root" $root)) | nindent 2 -}}
{{- /* We accept this means that the ConfigMap & all hash labels using this helper changes on every chart version upgrade and the HAProxy will restart as a result.
When we have a process to watch for file changes and send a reload signal to HAProxy this can move out of this helper and into the `ConfigMap` proper. */}}
ess-version.json: |-
  {"version": "{{ $root.Chart.Version }}", "edition": "community"}
{{- end -}}

{{- define "element-io.synapse.render-config-container" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.render-config-container missing context" .context }}
{{- $processType := required "element-io.synapse.render-config-container context required processType" .processType -}}
{{- $isHook := required "element-io.synapse.render-config-container context required isHook" .isHook -}}
{{- include "element-io.ess-library.render-config-container" (dict "root" $root "context"
            (dict "additionalPath" "synapse.additional"
                  "nameSuffix" "synapse"
                  "containerName" (.containerName | default "render-config")
                  "templatesVolume" (.templatesVolume | default "plain-config")
                  "underrides" (list "01-homeserver-underrides.yaml")
                  "overrides" (list "04-homeserver-overrides.yaml"
                                    (eq $processType "check-config" | ternary "05-main.yaml" (printf "05-%s.yaml" $processType)))
                  "outputFile" "homeserver.yaml"
                  "resources" .resources
                  "containersSecurityContext" .containersSecurityContext
                  "extraEnv" .extraEnv
                  "isHook" $isHook)) }}
{{- end }}
{{- end }}


{{- define "element-io.synapse.internal-hostport" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.internal-hostport missing context" .context -}}
{{- $root.Release.Name }}-synapse
{{- with .targetProcessType -}}
-{{ . }}
{{- end -}}
.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:8008
{{- end -}}
{{- end -}}
