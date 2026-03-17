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
	"time"

	"go.yaml.in/yaml/v2"
)

func generateExpiredKeys(existingSecretData map[string][]byte, generatedSecretsTypes map[string]SecretType) ([]byte, error) {
	// Generates yaml
	// old_signing_keys:
	//   ed25519:0:
	//     key: l/O9hxMVKB6Lg+3Hqf0FQQZhVESQcMzbPN1Cz2nM3og
	//     expired_ts: <current ts>

	output := make(map[string]map[string]any)
	for key, secretType := range generatedSecretsTypes {
		if secretType == SigningKey && mustBeRotated(existingSecretData, key) {
			expired := strings.TrimSpace(string(existingSecretData[key]))
			keyParts := strings.Split(expired, " ")
			keyId := keyParts[0] + ":" + keyParts[1]
			output[keyId] = make(map[string]any, 0)
			// We want to override the old key bytes of key id 0 with a new throwaway
			// public key to force old signatures to be invalid. This will force
			// servers to re-fetch all the old events which will now be signed with
			// the new key id 1.
			pub, _, err := ed25519.GenerateKey(nil)
			if err != nil {
				return nil, fmt.Errorf("failed to generate key: %w", err)
			}
			output[keyId]["key"] = base64.RawStdEncoding.EncodeToString(pub)
			output[keyId]["expired_ts"] = time.Now().UnixMilli()
		}
	}
	outputOldSigningKeys := make(map[string]map[string]map[string]any)
	if len(output) > 0 {
		outputOldSigningKeys["old_signing_keys"] = output
	}
	if outputYAML, err := yaml.Marshal(outputOldSigningKeys); err != nil {
		return nil, fmt.Errorf("error marshalling merged config to YAML: %w", err)
	} else {
		return outputYAML, nil
	}
}
