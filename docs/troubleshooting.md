<!--
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Troubleshooting

## Matrix RTC

### Error Code: `MISSING_MATRIX_RTC_FOCUS` when setting up a call

Matrix RTC must be able to fetch details of where the SFU and authorisation services are hosted. This is achieved by making requests to the Matrix client well-known file at `https://<server name>/.well-known/matrix/client`. This must happen over a HTTPS connection and the browser must trust the TLS certificates presented for this connection.

- Confirm that Matrix RTC isn't disabled in your deploy with `matrixRTC.enabled: false` (it is default enabled)
- Confirm `wellKnownDelegation` isn't disabled in your deploy with `wellKnownDelegation.enabled: false` (it is default enabled)
- Confirm the value of `serverName` is accessible over HTTPS and returns JSON: `https://<server name>/.well-known/matrix/client`
  - Confirm that the response body includes `org.matrix.msc4143.rtc_foci`
  - Confirm that the value of `livekit_service_url` is the value of `matrixRTC.ingress.host` with `https://` prefixed
- Confirm the value of `matrixRTC.ingress.host` is accessible over HTTPS and returns a HTTP 405: `https://<matrixRTC.ingress.host>/sfu/get`
