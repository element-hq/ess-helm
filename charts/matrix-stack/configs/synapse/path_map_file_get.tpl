{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}

# A map file that is used in haproxy config to map from matrix paths to the
# named backend. The format is: path_regexp backend_name
{{ if dig "client-reader" "enabled" false $root.Values.synapse.workers }}
{{- /*
The client-reader worker could also support the following GET requests
when the related workers are not enabled. To keep things simple, we don't support
this optimization here and we invite the chart user to directly deploy the related
workers instead if these requests path are under high load.

# push-rules
^/\_matrix/client/(api/v1|r0|v3|unstable)/pushrules/

# account-data
^/\_matrix/client/(r0|v3|unstable)/._/tags
^/\_matrix/client/(r0|v3|unstable)/._/account\_data

# presence
^/\_matrix/client/(api/v1|r0|v3|unstable)/presence/
*/}}
^/_matrix/client/unstable/org.matrix.msc4140/delayed_events client-reader
{{- end }}
