// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"encoding/base64"
	"regexp"
	"testing"
)

func TestGenerateSigningKey(t *testing.T) {
	testCases := []struct {
		name string
	}{
		{
			name: "Create signing key",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			synapseKey, err := generateSynapseSigningKey()
			if err != nil {
				t.Errorf("failed to generate signing key: %v", err)
			}
			expectedPattern := "ed25519 0 ([a-zA-Z0-9=\\/\\+]+)"
			if matches := regexp.MustCompile(expectedPattern).FindStringSubmatch(synapseKey); matches != nil {
				priv := matches[1]
				if privBytes, err := base64.StdEncoding.DecodeString(priv); err == nil {
					if len(privBytes) != 32 {
						t.Errorf("Invalid private key length: %d, expected 32", len(privBytes))
					}
				} else {
					t.Errorf("Failed to decode private key: %v", err)
				}
			} else {
				t.Fatalf("Unexpected key format: %v", synapseKey)
			}
		})
	}
}
