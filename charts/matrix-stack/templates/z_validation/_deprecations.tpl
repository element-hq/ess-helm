{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.deprecations" }}
{{- $root := .root }}
{{- $deprecations := list }}

{{- if and $root.Values.matrixRTC.enabled $root.Values.matrixRTC.sfu.enabled }}
  {{- range $filename, $details := $root.Values.matrixRTC.sfu.additional -}}
    {{- with $details.config }}
      {{- with . | fromYaml }}
        {{- if hasKey (.rtc | default dict) "use_external_ip" }}
          {{ $deprecations = append $deprecations (printf "matrixRTC.sfu.additional.%s.config contains rtc.use_external_ip.\n  Set matrixRTC.sfu.useStunToDiscoverPublicIP=%v in your values file instead.\n  Your setting will be ignored on 25.11 or later otherwise" $filename .rtc.use_external_ip) }}
        {{- end }}
        {{- if hasKey (.rtc | default dict) "node_ip" }}
          {{ $deprecations = append $deprecations (printf "matrixRTC.sfu.additional.%s.config contains rtc.node_ip.\n  Set matrixRTC.sfu.manualIP=%s in your values file instead.\n  Your setting will be ignored on 25.11 or later otherwise" $filename .rtc.node_ip) }}
        {{- end }}
      {{- end }}
    {{- end }}
    {{- with $details.configSecret }}
        {{ $deprecations = append $deprecations (printf "You're loading additional MatrixRTC SFU configuration via matrixRTC.sfu.additional.%s.configSecret + configSecretKey.\n  If these contain rtc.use_external_ip and/or rtc.node_ip these should be removed and replaced respectively with the matrix.RTC.sfu.useStunToDiscoverPublicIP and matrixRTC.sfu.manualIP values in your values file.\n  Your setting will be ignored on 25.11 or later otherwise" $filename) }}
    {{- end }}
  {{- end }}
{{- end }}

{{- with $root.Values.imagePullSecrets }}
  {{ $deprecations = append $deprecations "imagePullSecrets has entries. Please move to image.pullSecrets instead.\n  imagePullSecrets will be removed in 25.11 or later and cause schema validation failures" }}
{{- end }}

{{- if gt (len $deprecations) 0 }}
DEPRECATIONS. Please read me and update
{{- printf "\n- %s" ($deprecations | join "\n- " ) }}
{{- end }}
{{- end }}
