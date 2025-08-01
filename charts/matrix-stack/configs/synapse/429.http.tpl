{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

HTTP/1.0 429 Too Many Requests
Cache-Control: no-cache
Connection: close
Content-Type: application/json
access-control-allow-origin: *
access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
access-control-allow-headers: Origin, X-Requested-With, Content-Type, Accept, Authorization

{"errcode":"M_UNKNOWN","error":"Server is unavailable"}
