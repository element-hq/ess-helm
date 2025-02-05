// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
// internal/pkg/secret/secret.go

package secret

import (
	"context"
	"encoding/base64"
	"fmt"

	"math/rand"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/args"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
		"crypto/ed25519"
)

func GenerateSecret(client kubernetes.Interface, secretLabels map[string]string, namespace string, name string, key string, secretType args.SecretType) error {
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
		if managedBy, ok := existingSecret.ObjectMeta.Labels["app.kubernetes.io/managed-by"]; ok {
			if managedBy != "matrix-tools-init-secrets" {
				return fmt.Errorf("secret %s/%s is not managed by this matrix-tools-init-secrets", namespace, name)
			}
		} else {
			return fmt.Errorf("secret %s/%s is not managed by this matrix-tools-init-secrets", namespace, name)
		}
		// Make sure the labels are set correctly
		existingSecret.ObjectMeta.Labels = secretLabels
	}

	// Add or update the key in the data
	if existingSecret.Data == nil {
		existingSecret.Data = make(map[string][]byte)
	}
	if _, ok := existingSecret.Data[key]; !ok {
		switch secretType {
		case args.Rand32:
			randomString := generateRandomString(32)
			existingSecret.Data[key] = []byte(randomString)
		case args.SigningKey:
			if signingKey, err := generateSigningKey(); err == nil {
				existingSecret.Data[key] = []byte(signingKey)
			} else {
				return fmt.Errorf("failed to generate signing key: %w", err)
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

func generateRandomString(size int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	bytes := make([]byte, size)
	for i := range bytes {
		bytes[i] = charset[rand.Intn(len(charset))]
	}
	return string(bytes)
}

func generateSigningKey() (string, error) {
	_, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		return "", err
	}
	signingKey := fmt.Sprintf("ed25519 0 %s", base64.RawStdEncoding.EncodeToString(priv))
	return signingKey, nil
}
