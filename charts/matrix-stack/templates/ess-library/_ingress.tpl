{{- /*
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.ingress.annotations" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.annotations missing context" .context -}}
{{- $annotations := .extraAnnotations | default dict -}}
{{- with required "element-io.ess-library.ingress.annotations context missing ingress" .ingress }}
{{- $tlsSecret := coalesce .tlsSecret $root.Values.ingress.tlsSecret -}}
{{- if and (not $tlsSecret) $root.Values.certManager -}}
{{- with $root.Values.certManager -}}
{{- with .clusterIssuer -}}
{{- $annotations = mustMergeOverwrite (dict "cert-manager.io/cluster-issuer" .) $annotations -}}
{{- end -}}
{{- with .issuer -}}
{{- $annotations = mustMergeOverwrite (dict "cert-manager.io/issuer" .) $annotations -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $annotations = mustMergeOverwrite $annotations ($root.Values.ingress.annotations | deepCopy) -}}
{{- $annotations = mustMergeOverwrite $annotations (.annotations | deepCopy) -}}
{{- with $annotations -}}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.tls" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.tls missing context" .context -}}
{{- $ingress := required "element-io.ess-library.ingress.tls missing ingress" .ingress -}}
{{- $host := .host | default $ingress.host -}}
{{- $tlsEnabled := and $root.Values.ingress.tlsEnabled .ingress.tlsEnabled -}}
{{- $ingressName := required "element-io.ess-library.ingress.tls missing ingressName" .ingressName -}}
{{- if $tlsEnabled }}
tls:
{{- with (include "element-io.ess-library.ingress.tlsHostsSecret" (dict "root" $root "context" (dict "hosts" (list $host) "tlsSecret" $ingress.tlsSecret "ingressName" $ingressName))) }}
{{ . | nindent 2 }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.tlsHostsSecret" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.ingress.tlsHostsSecret missing context" .context -}}
{{- $ingressName := required "element-io.ess-library.ingress.tlsHostsSecret missing ingress name" .ingressName -}}
{{- $hosts := .hosts -}}
{{- $tlsSecret := coalesce .tlsSecret $root.Values.ingress.tlsSecret -}}
- hosts:
{{- range $host := $hosts }}
  - {{ (tpl $host $root) | quote }}
{{- end }}
{{ if or $tlsSecret $root.Values.certManager }}
  secretName: {{ (tpl ($tlsSecret | default (printf "{{ .Release.Name }}-%s-certmanager-tls" $ingressName))  $root) | quote }}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.className" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress.className missing context" -}}
{{- end }}
{{- with coalesce .context $root.Values.ingress.className -}}
ingressClassName: {{ . | quote }}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress-controller-type" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress-controller-type missing context" -}}
{{- end -}}
{{- with coalesce .context $root.Values.ingress.controllerType -}}
{{- . -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.ingress.ingress-nginx-dot-path-type" -}}
{{- $root := .root -}}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.ingress.ingress-nginx-dot-path-type missing context" -}}
{{- end -}}
{{- if eq (include "element-io.ess-library.ingress-controller-type" (dict "root" $root "context" .context)) "ingress-nginx" -}}
ImplementationSpecific
{{- else -}}
Prefix
{{- end -}}
{{- end -}}
