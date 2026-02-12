// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"encoding/base64"
	"fmt"
	"maps"
	"slices"
	"strconv"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"go.yaml.in/yaml/v2"
)

func TestGenerateExpiredKeys(t *testing.T) {
	t.Run("test generate expired keys", func(t *testing.T) {
		before := time.Now().UnixMilli()
		existingSecretData := map[string][]byte{"SECRET_KEY": []byte("ed25519 0 Ozi/KgL1WiuGMmp/GUME26bMWtqH92jF036tK6SIks4")}
		generatedSecretsTypes := map[string]SecretType{"SECRET_KEY": SigningKey}
		expiredKeysAsBytes, err := generateExpiredKeys(existingSecretData, generatedSecretsTypes)
		assert.NoError(t, err, "error generating expired keys: %v", err)
		assert.NotEmpty(t, expiredKeysAsBytes)
		var data map[string]map[string]map[string]string
		err = yaml.Unmarshal([]byte(expiredKeysAsBytes), &data)
		assert.NoError(t, err)
		assert.Contains(t, slices.Collect(maps.Keys(data["old_signing_keys"])), "ed25519:0")
		timestamp := data["old_signing_keys"]["ed25519:0"]["expired_ts"]
		assert.NotEmpty(t, timestamp, "ed25519:0.expired_ts is empty")
		decodedKey, err := base64.RawStdEncoding.DecodeString(data["old_signing_keys"]["ed25519:0"]["key"])
		assert.NoError(t, err, "error decoding base64 string: %v", err)
		assert.Equal(t, len(decodedKey), 32, "decoded key should be 32 bytes long")

		assert.NotEqual(t, decodedKey, []byte("AZT9wvov/MBB0/8SBFtzyG5P+V/2YqXu6Cq99EotC3U="))

		tsAsNumberInt, err := strconv.Atoi(timestamp)
		if err != nil {
			fmt.Println(err)
		}
		assert.LessOrEqual(t, int64(tsAsNumberInt), time.Now().UnixMilli())
		assert.LessOrEqual(t, before, int64(tsAsNumberInt))
		if err != nil {
			fmt.Println(err)
		}
	})
}

func TestGenerateNoExpiredKeys(t *testing.T) {
	t.Run("test generate expired keys", func(t *testing.T) {
		existingSecretData := map[string][]byte{"SECRET_KEY": []byte("ed25519 1 onKBAf8+AkpLkeqTeI7pdR6lKoAq4Hh9pV1AcDWTQvM")}
		generatedSecretsTypes := map[string]SecretType{"SECRET_KEY": SigningKey}
		expiredKeysAsBytes, err := generateExpiredKeys(existingSecretData, generatedSecretsTypes)
		if err != nil {
			t.Errorf("Error generating expired keys: %v", err)
		}
		assert.NotEmpty(t, expiredKeysAsBytes)
		var data map[string]map[string]map[string]string
		err = yaml.Unmarshal([]byte(expiredKeysAsBytes), &data)
		assert.NoError(t, err)
		assert.Empty(t, data)
	})
}

func TestGenerateInitially(t *testing.T) {
	t.Run("test generate expired keys", func(t *testing.T) {
		existingSecretData := map[string][]byte{}
		generatedSecretsTypes := map[string]SecretType{"SECRET_KEY": SigningKey}
		expiredKeysAsBytes, err := generateExpiredKeys(existingSecretData, generatedSecretsTypes)
		if err != nil {
			t.Errorf("Error generating expired keys: %v", err)
		}
		assert.NotEmpty(t, expiredKeysAsBytes)
		var data map[string]map[string]map[string]string
		err = yaml.Unmarshal([]byte(expiredKeysAsBytes), &data)
		assert.NoError(t, err)
		assert.Empty(t, data)
	})
}
