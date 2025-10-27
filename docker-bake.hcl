// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

// Targets filled by GitHub Actions: one for the regular tag
target "docker-metadata-action" {}

target "matrix-tools" {
  inherits = ["docker-metadata-action"]
  dockerfile = "Dockerfile"
  context = "./matrix-tools"
}
