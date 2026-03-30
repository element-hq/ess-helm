{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
report_stats: false

require_auth_for_profile_requests: true

federation_client_minimum_tls_version: '1.2'

experimental_features:
  msc4028_push_encrypted_events: true

database:
  args:
{{- with $root.Values.synapse.postgres }}
{{- if eq (.sslMode | default "prefer") "verify-full" }}
    {{- /*
    Use the system CA trust store if verify-full is set
    As per https://www.postgresql.org/docs/18/libpq-connect.html#LIBPQ-CONNECT-SSLROOTCERT
    it is an error to set this on 'weaker' sslmodes
    */}}
    sslrootcert: system
{{- end }}
{{- end }}
    # Synapse has no defaults, so up from Twisted's defaults of 3-5
    cp_min: 5
    cp_max: 10

{{- if $root.Values.matrixRTC.enabled }}
# The maximum allowed duration by which sent events can be delayed, as
# per MSC4140.
max_event_delay_duration: 24h

rc_message:
  # This needs to match at least e2ee key sharing frequency plus a bit of headroom
  # Note key sharing events are bursty
  per_second: 0.5
  burst_count: 30

rc_delayed_event_mgmt:
  # This needs to match at least the heart-beat frequency plus a bit of headroom
  # Currently the heart-beat is every 5 seconds which translates into a rate of 0.2s
  per_second: 1
  burst_count: 20
{{- end }}
