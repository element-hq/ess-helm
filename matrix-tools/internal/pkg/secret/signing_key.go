// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"crypto/ed25519"
	"encoding/base64"
	"fmt"
	"strings"
)

type SigningKeyData struct {
	Alg     string
	Version string
	Key     []byte
}

const BAD_SIGNING_KEY_ID = "ed25519 0"

func mustBeRotated(existingSecretData map[string][]byte, key string) bool {
	if value, ok := existingSecretData[key]; ok &&
		strings.HasPrefix(strings.TrimSpace(string(value)), BAD_SIGNING_KEY_ID) {
		return true
	}
	return false
}

func generateSigningKey(version string) (*SigningKeyData, error) {
	_, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		return nil, fmt.Errorf("failed to generate key: %w", err)
	}

	// The priv key is made of 32 bytes of private key, and 32 bytes of public key
	// Synapse only wants the first 32 bytes of the private key
	key := make([]byte, 32)
	copy(key, priv)

	return &SigningKeyData{
		Alg:     "ed25519",
		Version: version,
		Key:     key,
	}, nil
}

func encodeSigningKeyBase64(key *SigningKeyData) string {
	return base64.RawStdEncoding.EncodeToString(key.Key)
}

func generateSynapseSigningKey(version string) (string, error) {
	signingKey, err := generateSigningKey(version)
	if err != nil {
		return "", fmt.Errorf("failed to generate signing key: %w", err)
	}

	return fmt.Sprintf("%s %s %s\n", signingKey.Alg, signingKey.Version, encodeSigningKeyBase64(signingKey)), nil
}
