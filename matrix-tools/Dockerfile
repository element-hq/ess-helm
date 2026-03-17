# Copyright 2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

FROM --platform=${BUILDPLATFORM} golang:1.25 AS buildstage

WORKDIR /app
COPY . /app

RUN go env -w GOCACHE=/go-cache
RUN go env -w GOMODCACHE=/gomod-cache

RUN --mount=type=cache,target=/gomod-cache \
  go mod download

ARG TARGETOS TARGETARCH
RUN --mount=type=cache,target=/gomod-cache \
    --mount=type=cache,target=/go-cache \
  GOOS=$TARGETOS GOARCH=$TARGETARCH CGO_ENABLED=0 go build -o /app/matrix-tools cmd/main.go

FROM gcr.io/distroless/cc-debian13
WORKDIR /

COPY --from=buildstage --chmod=0755 /app/matrix-tools /
EXPOSE 8443
ENTRYPOINT ["/matrix-tools"]

USER 30000
