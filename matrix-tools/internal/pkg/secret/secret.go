// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only
// internal/pkg/secret/secret.go

package secret

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"math/big"
	"strconv"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

type SecretType int

const (
	UnknownSecretType SecretType = iota
	Rand32
	SigningKey
	Hex32
	Registration
	RSA
	EcdsaPrime256v1
)

func GenerateSecret(client kubernetes.Interface, secretLabels map[string]string,
	namespace string, name string, key string, secretType SecretType, generatorArgs []string) error {
	ctx := context.Background()

	secretsClient := client.CoreV1().Secrets(namespace)
	secretMeta := metav1.ObjectMeta{
		Name:      name,
		Namespace: namespace,
		Labels:    secretLabels,
	}
	// Fetch the existing secret or initialize an empty one
	existingSecret, err := secretsClient.Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		existingSecret, err = secretsClient.Create(ctx, &corev1.Secret{
			ObjectMeta: secretMeta, Data: nil}, metav1.CreateOptions{},
		)
		if err != nil {
			return fmt.Errorf("failed to initialize secret: %w", err)
		}
	} else {
		if managedBy, ok := existingSecret.Labels["app.kubernetes.io/managed-by"]; ok {
			if managedBy != "matrix-tools-init-secrets" {
				return fmt.Errorf("secret %s/%s is not managed by this matrix-tools-init-secrets", namespace, name)
			}
		} else {
			return fmt.Errorf("secret %s/%s is not managed by this matrix-tools-init-secrets", namespace, name)
		}
		// Make sure the labels are set correctly
		existingSecret.Labels = secretLabels
	}

	// Add or update the key in the data
	if existingSecret.Data == nil {
		existingSecret.Data = make(map[string][]byte)
	}
	if _, ok := existingSecret.Data[key]; !ok {
		switch secretType {
		case Rand32:
			if randomString, err := generateRandomString(32); err == nil {
				existingSecret.Data[key] = randomString
			}
		case SigningKey:
			if signingKey, err := generateSynapseSigningKey(); err == nil {
				existingSecret.Data[key] = []byte(signingKey)
			} else {
				return fmt.Errorf("failed to generate signing key: %w", err)
			}
		case Hex32:
			if hexBytes, err := generateRandomBytesHex(32); err == nil {
				existingSecret.Data[key] = hexBytes
			} else {
				return fmt.Errorf("failed to generate Hex32 : %w", err)
			}
		case RSA:
			bits, err := strconv.Atoi(generatorArgs[0])
			if err != nil {
				return fmt.Errorf("failed to parse bits for RSA key: %w", err)
			}
			if keyBytes, err := generateRSA(bits, generatorArgs[1]); err == nil {
				existingSecret.Data[key] = keyBytes
			} else {
				return fmt.Errorf("failed to generate RSA key: %w", err)
			}
		case EcdsaPrime256v1:
			if keyBytes, err := generateEcdsaPrime256v1DER(); err == nil {
				existingSecret.Data[key] = keyBytes
			} else {
				return fmt.Errorf("failed to generate ECDSA Prime256v1 key: %w", err)
			}
		case Registration:
			if registrationString, err := generateRegistration(generatorArgs[0]); err == nil {
				existingSecret.Data[key] = registrationString
			} else {
				return fmt.Errorf("failed to generate registration: %w", err)
			}
		default:
			return fmt.Errorf("unknown secret type for: %s:%s", name, key)
		}
	}

	_, err = secretsClient.Update(ctx, existingSecret, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("failed to update secret: %w", err)
	}
	fmt.Printf("Successfully updated secret: %s:%s\n", name, key)
	return nil
}

func generateRandomString(size int) ([]byte, error) {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	bytes := make([]byte, size)
	for i := range bytes {
		randIndex, err := rand.Int(rand.Reader, big.NewInt(int64(len(charset))))
		if err != nil {
			return nil, fmt.Errorf("failed to generate random string : %w", err)
		}
		bytes[i] = charset[randIndex.Int64()]
	}
	return bytes, nil
}

func generateRandomBytesHex(size int) ([]byte, error) {
	key := make([]byte, size)
	if _, err := rand.Read(key); err != nil {
		return nil, fmt.Errorf("failed to generate key : %w", err)
	}
	encodedKey := make([]byte, hex.EncodedLen(len(key)))
	hex.Encode(encodedKey, key)
	return encodedKey, nil
}
