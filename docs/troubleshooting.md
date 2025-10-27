<!--
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

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

If your `serverName` is accessible with public DNS over the internet you can use https://federationtester.matrix.org/ to validate that it is accessible and has a generally trusted TLS certificate.

### Matrix RTC authoriser logs say `Failed to look up user info`

The Matrix RTC authoriser must be able to query Matrix servers (including your own) to determine who is attempting to connect to it. It uses the Matrix Federation APIs for this.

As a result the authoriser `Pod` must be able to reach both the `https://<server name>/.well-known/matrix/server` endpoint and `https://<synapse.ingress.host>/_matrix/federation/v1/openid/userinfo` (amongst other things). Symptoms of problems in this area include logging in the authoriser `Pod` saying it can't connect to port `8448`

- Confirm `wellKnownDelegation` isn't disabled in your deploy with `wellKnownDelegation.enabled: false` (it is default enabled)
- Confirm the value of `serverName` is accessible over HTTPS and returns JSON: `https://<server name>/.well-known/matrix/server`
  - Confirm that the value of `m.server` is the value of `synapse.ingress.host` with `:443` suffixed
- Confirm the value of `synapse.ingress.host` is accessible over HTTPS and returns JSON: `https://<synapse.ingress.host>/_matrix/key/v2/server`

If these all work outside of the cluster, it maybe that the `Pods` inside the cluster can't access them. You can tell the Matrix RTC authoriser to directly hit your ingress controller IP

```yaml
matrixRTC:
  hostAliases:
  - hostnames:
    - ess.localhost
    - mrtc.ess.localhost
    - synapse.ess.localhost
    ip: '<the spec.clusterIP of your Ingress Controller's Service>'
```

If you are using a TLS certificate signed by a certificate authority that isn't in standard TLS trust stores (i.e. it is own your) you will need to disable TLS verification in the Matrix RTC authoriser with

```yaml
matrixRTC:
  extraEnv:
  - name: LIVEKIT_INSECURE_SKIP_VERIFY_TLS
    value: YES_I_KNOW_WHAT_I_AM_DOING
```

### Matrix RTC SFU is stuck in `CrashLoopBackOff` without any log

This typically means that the SFU is attempting to perform a STUN request to resolve its advertised IP address, and it is failing.

By default, the SFU tries to connect to Google's STUN servers. You can try the following:

- Ensure that the SFU can reach the Google STUN servers.
- Change the STUN servers configured in the Matrix RTC SFU.
- Force the SFU to use a manual IP address instead of relying on STUN to resolve the advertised IP.

For more information about the SFU networking, see [Matrix RTC Networking](./advanced.md#networking).
