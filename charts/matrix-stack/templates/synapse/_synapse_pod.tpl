{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.synapse.pod-template" }}
{{- $root := .root }}
{{- with required "element-io.synapse.pod-template requires context" .context }}
{{- $processType := required "element-io.synapse.pod-template requires context.processType" .processType }}
{{- $isHook := required "element-io.synapse-pod-template requires context.isHook" .isHook -}}
{{- $enabledWorkers := (include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson }}
template:
  metadata:
    labels:
{{- if $isHook }}
      {{- include "element-io.synapse-check-config-hook.labels" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" false)) | nindent 6 }}
{{- else }}
      {{- include "element-io.synapse.process.labels" (dict "root" $root "context" (dict "image" .image "labels" .labels "withChartVersion" false "isHook" $isHook "processType" $processType)) | nindent 6 }}
{{- end }}
      k8s.element.io/synapse-config-hash: "{{ include "element-io.synapse.configmap-data"  (dict "root" $root "context" .) | sha1sum }}"
      k8s.element.io/synapse-secret-hash: "{{ include "element-io.synapse.secret-data"  (dict "root" $root "context" .) | sha1sum }}"
{{- range $index, $appservice := .appservices }}
{{- if .configMap }}
      k8s.element.io/as-registration-{{ $index }}-hash: "{{ (lookup "v1" "ConfigMap" $root.Release.Namespace (tpl $appservice.configMap $root)) | toJson | sha1sum }}"
{{- else }}
      k8s.element.io/as-registration-{{ $index }}-hash: "{{ (lookup "v1" "Secret" $root.Release.Namespace (tpl $appservice.secret $root)) | toJson | sha1sum }}"
{{- end }}
{{- end }}
      {{ include "element-io.ess-library.postgres-label" (dict "root" $root "context" (dict
                                                              "essPassword" "synapse"
                                                              "postgresProperty" .postgres
                                                              )
                                          ) -}}
{{- with .annotations }}
    annotations:
      {{- toYaml . | nindent 6 }}
{{- end }}
  spec:
{{- if $isHook }}
    restartPolicy: Never
{{- end }}
{{- include "element-io.ess-library.pods.commonSpec"
            (dict "root" $root "context"
                                    (dict "componentValues" .
                                          "instanceSuffix" ($isHook | ternary "synapse-check-config-hook" (printf "synapse-%s" $processType))
                                          "serviceAccountNameSuffix" ($isHook | ternary "synapse-check-config-hook" "synapse")
                                          "deployment" false
                                          "usesMatrixTools" true)
                                    ) | nindent 4 }}
{{- with .hostAliases }}
    hostAliases:
      {{- tpl (toYaml . | nindent 6) $root }}
{{- end }}
{{- /*
We have an init container to render & merge the config for several reasons:
* We have external, user-supplied Secrets and don't want to use `lookup` as that doesn't work with things like ArgoCD
* We want to treat credentials provided in Helm the same as credentials in external Secrets
* We want to guarantee the order the YAML files are merged and while we can code to Synapse's current behavour that may change
* We could do this all in the main Synapse container but then there's potential confusion between `/config-templates`, `/conf` in the image and `/conf` the `emptyDir`
*/}}
    initContainers:
    - name: render-config
{{- with $root.Values.matrixTools.image -}}
{{- if .digest }}
      image: "{{ .registry }}/{{ .repository }}@{{ .digest }}"
      imagePullPolicy: {{ .pullPolicy | default "IfNotPresent" }}
{{- else }}
      image: "{{ .registry }}/{{ .repository }}:{{ required "matrixTools.image.tag is required if no digest" .tag }}"
      imagePullPolicy: {{ .pullPolicy | default "Always" }}
{{- end }}
{{- end }}
{{- with .containersSecurityContext }}
      securityContext:
        {{- toYaml . | nindent 8 }}
{{- end }}
      command:
      - "/matrix-tools"
      - render-config
      - -output
      - /conf/homeserver.yaml
      - /config-templates/01-homeserver-underrides.yaml
        {{- range $key := (.additional | keys | uniq | sortAlpha) -}}
        {{- $prop := index $root.Values.synapse.additional $key }}
        {{- if $prop.config }}
      - /secrets/{{ (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook))) }}/user-{{ $key }}
        {{- end }}
        {{- if $prop.configSecret }}
      - /secrets/{{ tpl $prop.configSecret $root }}/{{ $prop.configSecretKey }}
        {{- end }}
        {{- end }}
      - /config-templates/04-homeserver-overrides.yaml
{{- if eq $processType "check-config-hook" }}
      - /config-templates/05-main.yaml
{{- else }}
      - /config-templates/05-{{ $processType }}.yaml
{{- end }}
      env:
        {{- include "element-io.synapse.matrixToolsEnv" (dict "root" $root "context" .) | nindent 8 }}
        {{- include "element-io.synapse.env" (dict "root" $root "context" .) | nindent 8 }}
{{- with .resources }}
      resources:
        {{- toYaml . | nindent 8 }}
{{- end }}
      volumeMounts:
      - mountPath: /config-templates
        name: plain-config
        readOnly: true
{{- range $secret := include "element-io.synapse.configSecrets" (dict "root" $root "context" .) | fromJsonArray }}
      - mountPath: /secrets/{{ tpl $secret $root }}
        name: "secret-{{ tpl $secret $root }}"
        readOnly: true
{{- end }}
      - mountPath: /conf
        name: rendered-config
        readOnly: false
{{- if ne $processType "check-config-hook" }}
    - name: db-wait
{{- with $root.Values.matrixTools.image -}}
{{- if .digest }}
      image: "{{ .registry }}/{{ .repository }}@{{ .digest }}"
      imagePullPolicy: {{ .pullPolicy | default "IfNotPresent" }}
{{- else }}
      image: "{{ .registry }}/{{ .repository }}:{{ required "matrixTools.image.tag is required if no digest" .tag }}"
      imagePullPolicy: {{ .pullPolicy | default "Always" }}
{{- end }}
{{- end }}
{{- with .containersSecurityContext }}
      securityContext:
        {{- toYaml . | nindent 8 }}
{{- end }}
      command:
      - "/matrix-tools"
      - tcpwait
      - -address
      - {{ include "element-io.ess-library.postgres-host-port" (dict "root" $root "context" (dict "postgres" .postgres)) | quote }}
{{- with .resources }}
      resources:
        {{- toYaml . | nindent 8 }}
{{- end }}
{{- end }}
    containers:
    - name: synapse
{{- with .image -}}
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
        {{- toYaml . | nindent 8 }}
{{- end }}
      command:
      - "python3"
      - "-m"
      - {{ include "element-io.synapse.process.app" (dict "root" $root "context" $processType) }}
      - "-c"
      - /conf/homeserver.yaml
{{- range .extraArgs }}
      - {{ . | quote }}
{{- end }}
      env:
        {{- include "element-io.synapse.pythonEnv" (dict "root" $root "context" .) | nindent 8 }}
        {{- include "element-io.synapse.env" (dict "root" $root "context" .) | nindent 8 }}
{{- if not $isHook }}
      ports:
{{- if (include "element-io.synapse.process.hasHttp" (dict "root" $root "context" $processType)) }}
      - containerPort: 8008
        name: synapse-http
        protocol: TCP
{{- end }}
{{- if (include "element-io.synapse.process.hasReplication" (dict "root" $root "context" $processType)) }}
      - containerPort: 9093
        name: synapse-repl
        protocol: TCP
{{- end }}
      - containerPort: 8080
        name: synapse-health
        protocol: TCP
      - containerPort: 9001
        name: synapse-metrics
        protocol: TCP
      startupProbe: {{- include "element-io.ess-library.pods.probe" .startupProbe | nindent 8 }}
        httpGet:
          path: /health
          port: synapse-health
      livenessProbe: {{- include "element-io.ess-library.pods.probe" .livenessProbe | nindent 8 }}
        httpGet:
          path: /health
          port: synapse-health
      readinessProbe: {{- include "element-io.ess-library.pods.probe" .readinessProbe | nindent 8 }}
        httpGet:
          path: /health
          port: synapse-health
{{- end }}
{{- with .resources }}
      resources:
        {{- toYaml . | nindent 8 }}
{{- end }}
      volumeMounts:
{{- range $secret := include "element-io.synapse.configSecrets" (dict "root" $root "context" .) | fromJsonArray }}
      - mountPath: /secrets/{{ tpl $secret $root }}
        name: "secret-{{ tpl $secret $root }}"
        readOnly: true
{{- end }}
{{- range $idx, $appservice := .appservices }}
      - name: as-{{ $idx }}
        readOnly: true
{{- if $appservice.configMap }}
        mountPath: "/as/{{ $idx }}/{{ $appservice.configMapKey }}"
        subPath: {{ $appservice.configMapKey | quote }}
{{- end -}}
{{- if $appservice.secret }}
        mountPath: "/as/{{ $idx }}/{{ $appservice.secretKey }}"
        subPath: {{ $appservice.secretKey | quote }}
{{- end -}}
{{- end }}
      - mountPath: /conf/log_config.yaml
        name: plain-config
        subPath: log_config.yaml
        readOnly: false
      - mountPath: /conf
        name: rendered-config
        readOnly: false
      - mountPath: /media
        name: media
        readOnly: false
      - mountPath: /tmp
        name: tmp
        readOnly: false
    volumes:
    - configMap:
        defaultMode: 420
        name: {{ include "element-io.synapse.configmap-name" (dict "root" $root "context" (dict "isHook" $isHook)) }}
      name: plain-config
{{- range $secret := include "element-io.synapse.configSecrets" (dict "root" $root "context" .) | fromJsonArray }}
    - secret:
        secretName: {{ tpl $secret $root }}
      name: secret-{{ tpl $secret $root }}
{{- end }}
    - emptyDir:
        medium: Memory
      name: "rendered-config"
{{- range $idx, $appservice := .appservices }}
    - name: as-{{ $idx }}
{{- with $appservice.configMap }}
      configMap:
        defaultMode: 420
        name: "{{ tpl . $root }}"
{{- end }}
{{- with $appservice.secret }}
      secret:
        secretName: "{{ tpl . $root }}"
{{- end }}
{{- end }}
{{- if (include "element-io.synapse.process.responsibleForMedia" (dict "root" $root "context" (dict "processType" $processType "enabledWorkerTypes" (keys $enabledWorkers)))) }}
    - persistentVolumeClaim:
        claimName: {{ include "element-io.synapse.pvcName" (dict "root" $root "context" .) }}
      name: "media"
{{- else }}
    - emptyDir:
        medium: Memory
      name: "media"
{{- end }}
    - emptyDir:
        medium: Memory
      name: "tmp"
{{- end }}
{{- end }}
