{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}


{{- define "element-io.ess-library.workloads.commonSpec" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.workloads.commonSpec missing context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.workloads.commonSpec missing context.nameSuffix" .nameSuffix -}}
{{- $serviceNameSuffix := .serviceNameSuffix | default $nameSuffix -}}
{{- $kind := required "element-io.ess-library.workloads.commonSpec missing context.kind" .kind -}}
{{- with required "element-io.ess-library.workloads.commonSpec missing context.componentValues" .componentValues -}}
replicas: {{ .replicas | default 1 }}
selector:
  matchLabels:
    app.kubernetes.io/instance: {{ $root.Release.Name }}-{{ $nameSuffix }}
{{- if eq "Deployment" $kind }}
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 2
{{- if hasKey . "replicas" }}
    maxUnavailable: {{ min (max 0 (sub .replicas 1)) 1 }}
{{- else }}
    maxUnavailable: 0
{{- end }}
{{- else }}
serviceName: {{ $root.Release.Name }}-{{ $serviceNameSuffix }}
updateStrategy:
  type: RollingUpdate
{{- if ne "postgres" $nameSuffix }}
{{- /* Until we have a migration path in https://github.com/element-hq/ess-helm/pull/870 */}}
# Without this CrashLoopBackoffs due to config failures block pod recreation
podManagementPolicy: Parallel
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
