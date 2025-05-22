{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.synapse.process.hasHttp" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.hasHttp missing context" .context -}}
{{ $hasHttp := (list "main"
                     "client-reader"
                     "encryption"
                     "event-creator"
                     "federation-inbound"
                     "federation-reader"
                     "initial-synchrotron"
                     "media-repository"
                     "presence-writer"
                     "push-rules"
                     "receipts-account"
                     "sliding-sync"
                     "sso-login"
                     "synchrotron"
                     "typing-persister"
                     "user-dir") }}
{{- if has . $hasHttp -}}
hasHttp
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.hasReplication" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.hasReplication missing context" .context -}}
{{- $hasReplication := (list "main"
                             "encryption"
                             "event-persister"
                             "push-rules"
                             "presence-writer"
                             "receipts-account"
                             "typing-persister") }}
{{- if has . $hasReplication -}}
hasReplication
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.isSingle" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.isSingle missing context" .context -}}
{{ $isSingle := (list "main"
                      "appservice"
                      "background"
                      "encryption"
                      "media-repository"
                      "presence-writer"
                      "push-rules"
                      "receipts-account"
                      "sso-login"
                      "typing-persister"
                      "user-dir") }}
{{- if has . $isSingle -}}
isSingle
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.canFallbackToMain" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.canFallbackToMain missing context" .context -}}
{{ $cantFallBackToMain := (list "media-repository" "sso-login") }}
{{- if not (has . $cantFallBackToMain) -}}
canFallback
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.workerTypeName" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.workerTypeName missing context" .context -}}
{{- if eq . "initial-synchrotron" -}}
initial-sync
{{- else -}}
{{ . }}
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.app" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.app missing context" .context -}}
{{- if eq . "main" -}}
synapse.app.homeserver
{{- else if eq . "media-repository" -}}
synapse.app.media_repository
{{- else if eq . "check-config-hook" -}}
synapse.config
{{- else -}}
synapse.app.generic_worker
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.responsibleForMedia" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.responsibleForMedia missing context" .context -}}
{{- if and (eq .processType "main") (not (has "media-repository" .enabledWorkerTypes)) -}}
responsibleForMedia
{{- else if eq .processType "media-repository" -}}
responsibleForMedia
{{- end -}}
{{- end -}}
{{- end }}

{{- define "element-io.synapse.process.streamWriters" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.streamWriters missing context" .context -}}
{{- if eq . "encryption" }}
{{ list "to_device" | toJson }}
{{- else if eq . "event-persister" }}
{{ list "events" | toJson }}
{{- else if eq . "presence-writer" }}
{{ list "presence" | toJson }}
{{- else if eq . "push-rules" }}
{{ list "push_rules" | toJson }}
{{- else if eq . "receipts-account" }}
{{ list "account_data" "receipts" | toJson }}
{{- else if eq . "typing-persister" }}
{{ list "typing" | toJson }}
{{- else -}}
{{ list | toJson }}
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.streamWriterWorkers" -}}
{{- $root := .root -}}
{{ $streamWriterWorkers := list }}
{{- range $workerType := keys ((include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson) }}
{{- if include "element-io.synapse.process.streamWriters" (dict "root" $root "context" $workerType) | fromJsonArray -}}
{{ $streamWriterWorkers = append $streamWriterWorkers $workerType }}
{{- end }}
{{- end }}
{{ $streamWriterWorkers | toJson }}
{{- end }}

{{- define "element-io.synapse.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.configSecrets missing context" .context -}}
{{- $isHook := required "element-io.synapse.configSecrets requires context.isHook" .isHook -}}
{{ $configSecrets := list (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook))) }}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- $configSecrets = append $configSecrets (include "element-io.ess-library.postgres-secret-name"
                                            (dict "root" $root "context" (dict
                                                                "essPassword" "synapse"
                                                                "componentPasswordPath" "synapse.postgres.password"
                                                                "defaultSecretName" (include "element-io.synapse.secret-name" (dict "root" $root "context" (dict "isHook" $isHook)))
                                                                "isHook" .isHook
                                                                )
                                            )
                                        ) -}}
{{- if (and $root.Values.matrixAuthenticationService.enabled (not $root.Values.matrixAuthenticationService.preMigrationSynapseHandlesAuth)) }}
{{- with $root.Values.matrixAuthenticationService -}}
  {{- with .synapseSharedSecret -}}
    {{- with .value -}}
    {{- $configSecrets = append $configSecrets (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" (dict "isHook" $isHook))) -}}
    {{- end -}}
    {{- with .secret -}}
    {{ $configSecrets = append $configSecrets (tpl . $root) }}
    {{- end -}}
  {{- end -}}
  {{- with .synapseOIDCClientSecret -}}
    {{- with .value -}}
    {{- $configSecrets = append $configSecrets (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" (dict "isHook" $isHook))) -}}
    {{- end -}}
    {{- with .secret -}}
    {{ $configSecrets = append $configSecrets (tpl . $root) }}
    {{- end -}}
  {{- end -}}
{{- end -}}
{{- end -}}
{{- with .macaroon.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .registrationSharedSecret.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .signingKey.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .additional -}}
{{- range $key := (. | keys | uniq | sortAlpha) -}}
{{- $prop := index $root.Values.synapse.additional $key }}
{{- if $prop.configSecret }}
{{ $configSecrets = append $configSecrets (tpl $prop.configSecret $root) }}
{{- end }}
{{- end }}
{{- end }}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.synapse.process.workerPaths" -}}
{{- $root := .root -}}
{{- with required "element-io.synapse.process.workerPaths missing context" .context -}}
{{ $workerPaths := list }}

{{- if eq .workerType "client-reader" }}
{{- /* Client API requests (apart from createRoom which is eventCreator) */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/publicRooms$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/joined_members$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/context/.*$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/members$"
) }}
{{- /* We can't guarantee this goes to the same instance.
      But it is a federated request. A misconfiguration seems to generate a really small volume
      of bad requests on matrix.org. For ease of maintenance we are routing it to the
      client-reader pool as the other requests. Should be fixed by:
      https://github.com/matrix-org/synapse/issues/11717 */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/messages$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/state$"
  "^/_matrix/client/v1/rooms/.*/hierarchy$"
  "^/_matrix/client/(v1|unstable)/rooms/.*/relations/"
  "^/_matrix/client/v1/rooms/.*/threads$"
  "^/_matrix/client/unstable/im.nheko.summary/summary/.*$"
  "^/_matrix/client/(r0|v3|unstable)/account/3pid$"
  "^/_matrix/client/(r0|v3|unstable)/account/whoami$"
  "^/_matrix/client/(r0|v3|unstable)/devices$"
  "^/_matrix/client/versions$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/voip/turnServer$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/event/"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/joined_rooms$"
  "^/_matrix/client/v1/rooms/.*/timestamp_to_event$"
  "^/_matrix/client/(api/v1|r0|v3|unstable/.*)/rooms/.*/aliases"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/search$"
  "^/_matrix/client/(r0|v3|unstable)/user/.*/filter(/|$)"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/directory/room/.*$"
  "^/_matrix/client/(r0|v3|unstable)/capabilities$"
  "^/_matrix/client/(r0|v3|unstable)/notifications$"
  "^/_synapse/admin/v1/rooms/"
) }}

{{- /* Registration/login requests */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/login$"
  "^/_matrix/client/(r0|v3|unstable)/register$"
  "^/_matrix/client/(r0|v3|unstable)/register/available$"
  "^/_matrix/client/v1/register/m.login.registration_token/validity$"
  "^/_matrix/client/(r0|v3|unstable)/password_policy$"
) }}

{{- /* Encryption requests */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(r0|v3|unstable)/keys/query$"
  "^/_matrix/client/(r0|v3|unstable)/keys/changes$"
) }}

{{- /* On m.org /keys/claim & /room_keys go to the encryption worker but the above 2 go to client-reader
       https://github.com/matrix-org/synapse/pull/11599 makes no claim that there are efficency
       reasons to go to the encryption worker, so put them on the client-reader */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(r0|v3|unstable)/keys/claim$"
  "^/_matrix/client/(r0|v3|unstable)/room_keys/"
  "^/_matrix/client/(r0|v3|unstable)/keys/upload"
) }}
{{- end }}

{{- if eq .workerType "encryption" }}
{{ $workerPaths = append $workerPaths
  "^/_matrix/client/(r0|v3|unstable)/sendToDevice/"
}}
{{- end }}

{{- if eq .workerType "event-creator" }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/redact"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/send"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/state/"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/(join|invite|leave|ban|unban|kick)$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/join/"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/knock/"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/profile/"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/createRoom$"
) }}
{{- end }}

{{- if eq .workerType "federation-inbound" }}
{{- /* Inbound federation transaction request */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/federation/v1/send/"
  )
}}
{{- end }}

{{- if eq .workerType "federation-reader" }}
{{- /* All Federation REST requests for generic_worker */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/federation/v1/version$"
  "^/_matrix/federation/v1/event/"
  "^/_matrix/federation/v1/state/"
  "^/_matrix/federation/v1/state_ids/"
  "^/_matrix/federation/v1/backfill/"
  "^/_matrix/federation/v1/get_missing_events/"
  "^/_matrix/federation/v1/publicRooms"
  "^/_matrix/federation/v1/query/"
  "^/_matrix/federation/v1/make_join/"
  "^/_matrix/federation/v1/make_leave/"
  "^/_matrix/federation/(v1|v2)/send_join/"
  "^/_matrix/federation/(v1|v2)/send_leave/"
  "^/_matrix/federation/v1/make_knock/"
  "^/_matrix/federation/v1/send_knock/"
  "^/_matrix/federation/(v1|v2)/invite/"
) }}

{{- /* Not in public docs but on matrix.org */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/federation/v1/query_auth/"
  "^/_matrix/federation/v1/event_auth/"
  "^/_matrix/federation/v1/timestamp_to_event/"
  "^/_matrix/federation/v1/exchange_third_party_invite/"
  "^/_matrix/federation/v1/user/devices/"
  "^/_matrix/key/v2/query"
  "^/_matrix/federation/v1/hierarchy/"
) }}
{{- end }}

{{- /* Route these paths to the initial-synchrotron is available otherwise use the standard synchrotron if we have it */}}
{{- if or (eq .workerType "initial-synchrotron") (and (eq .workerType "synchrotron") (not (has "initial-synchrotron" .enabledWorkerTypes))) }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3)/initialSync$"
  "^/_matrix/client/(api/v1|r0|v3)/rooms/[^/]+/initialSync$"
) }}
{{- end }}

{{- if eq .workerType "media-repository" }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/media/"
  "^/_matrix/client/v1/media/"
  "^/_matrix/federation/v1/media/"
  "^/_synapse/admin/v1/purge_media_cache$"
  "^/_synapse/admin/v1/room/.*/media.*"
  "^/_synapse/admin/v1/user/.*/media.*$"
  "^/_synapse/admin/v1/media/.*$"
  "^/_synapse/admin/v1/quarantine_media/.*$"
  "^/_synapse/admin/v1/users/.*/media$"
) }}
{{- end }}

{{- if eq .workerType "presence-writer" }}
{{ $workerPaths = append $workerPaths
  "^/_matrix/client/(api/v1|r0|v3|unstable)/presence/"
}}
{{- end }}

{{- if eq .workerType "push-rules" }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/pushrules/"
  "^/_matrix/client/unstable/org.matrix.msc4140/delayed_events"
) }}
{{- end }}

{{- if eq .workerType "receipts-account" }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(r0|v3|unstable)/.*/tags"
  "^/_matrix/client/(r0|v3|unstable)/.*/account_data"
  "^/_matrix/client/(r0|v3|unstable)/rooms/.*/receipt"
  "^/_matrix/client/(r0|v3|unstable)/rooms/.*/read_markers"
) }}
{{- end }}

{{- if eq .workerType "sliding-sync" }}
{{ $workerPaths = append $workerPaths
  "^/_matrix/client/unstable/org.matrix.simplified_msc3575/.*"
}}
{{- end }}

{{- if eq .workerType "sso-login" }}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(api/v1|r0|v3|unstable)/login/sso/redirect"
  "^/_synapse/client/pick_idp$"
  "^/_synapse/client/pick_username"
  "^/_synapse/client/new_user_consent$"
  "^/_synapse/client/sso_register$"
  "^/_synapse/client/oidc/callback$"
  "^/_synapse/client/saml2/authn_response$"
  "^/_matrix/client/(api/v1|r0|v3|unstable)/login/cas/ticket$"
) }}
{{- if (and $root.Values.matrixAuthenticationService.enabled (not $root.Values.matrixAuthenticationService.preMigrationSynapseHandlesAuth)) }}
{{ $workerPaths = concat $workerPaths (list
    "^/_synapse/admin/v2/users/[^/]+$"
    "^/_synapse/admin/v1/username_available$"
    "^/_synapse/admin/v1/users/[^/]+/_allow_cross_signing_replacement_without_uia$"
) }}
{{- end }}
{{- end }}

{{- if eq .workerType "synchrotron" }}
{{- /* Update the initial-synchrotron handling in the haproxy.cfg frontend when updating this */}}
{{ $workerPaths = concat $workerPaths (list
  "^/_matrix/client/(r0|v3)/sync$"
  "^/_matrix/client/(api/v1|r0|v3)/events$"
) }}
{{- end }}

{{- if eq .workerType "typing-persister" }}
{{ $workerPaths = append $workerPaths
  "^/_matrix/client/(api/v1|r0|v3|unstable)/rooms/.*/typing"
}}
{{- end }}

{{- if eq .workerType "user-dir" }}
{{ $workerPaths = append $workerPaths
  "^/_matrix/client/(r0|v3|unstable)/user_directory/search$"
}}
{{- end }}
{{ $workerPaths | toJson }}
{{- end }}
{{- end }}
