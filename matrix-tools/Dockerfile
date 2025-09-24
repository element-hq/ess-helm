# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

FROM --platform=${BUILDPLATFORM} golang:1.24 AS buildstage

WORKDIR /app
COPY . /app

RUN --mount=type=cache,target=/go/pkg/mod \
  go mod download

ARG TARGETOS TARGETARCH
RUN --mount=type=cache,target=/go/pkg/mod \
  GOOS=$TARGETOS GOARCH=$TARGETARCH CGO_ENABLED=0 go build -o /app/matrix-tools cmd/main.go

FROM gcr.io/distroless/cc-debian12
WORKDIR /

COPY --from=buildstage --chmod=0755 /app/matrix-tools /
EXPOSE 8443
ENTRYPOINT ["/matrix-tools"]

USER 30000
