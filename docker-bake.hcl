// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

// Targets filled by GitHub Actions: one for the regular tag
target "docker-metadata-action" {}

target "matrix-tools" {
  inherits = ["docker-metadata-action"]
  dockerfile = "Dockerfile"
  context = "./matrix-tools"
}

// The image the browser server runs in. The integration tests drive it
// (tests/integration/fixtures/playwright.py).
// Unlike matrix-tools it does not inherit the metadata target: it is not published under
// the regular tags. Its name and tag are computed by image_reference(). The tests and CI
// pass them with --set when they build the image, together with the playwright version.
target "playwright-browser" {
  dockerfile = "Dockerfile"
  context = "./tests/integration/fixtures/files/playwright"
}
