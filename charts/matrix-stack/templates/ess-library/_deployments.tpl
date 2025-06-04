{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}


{{- define "element-io.ess-library.deployments.commonSpec" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.deployments.commonSpec missing context" .context -}}
{{- if hasKey . "replicas" }}
replicas: {{ required (printf "element-io.ess-library.deployments.commonSpec with nameSuffix %s is missing a replicas value" .nameSuffix) .replicas }}
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: {{ min (max 0 (sub .replicas 1)) 1 }}
    maxSurge: 2
{{- else }}
replicas: 1
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 2
{{- end }}
selector:
  matchLabels:
    app.kubernetes.io/instance: {{ $root.Release.Name }}-{{ .nameSuffix }}
{{- end }}
{{- end }}
