// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"context"
	"reflect"
	"regexp"
	"testing"

	"github.com/stretchr/testify/assert/yaml"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	testclient "k8s.io/client-go/kubernetes/fake"
)

func TestGenerateSecret(t *testing.T) {
	testCases := []struct {
		name                string
		namespace           string
		initLabels          map[string]string
		secretLabels        map[string]string
		secretName          string
		secretKeys          []string
		secretType          SecretType
		secretData          map[string][]byte
		secretGeneratorArgs []string
		expectedError       bool
	}{
		{
			name:                "Create a new secret",
			namespace:           "create-secret",
			secretName:          "test-secret",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"app.kubernetes.io/name": "test-secret"},
			secretKeys:          []string{"key"},
			secretType:          Rand32,
			secretData:          nil,
			secretGeneratorArgs: make([]string, 0),
			expectedError:       false,
		},
		{
			name:                "Create a new signing key",
			namespace:           "create-secret",
			secretName:          "test-signing-key",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"app.kubernetes.io/name": "test-secret"},
			secretKeys:          []string{"key"},
			secretType:          SigningKey,
			secretData:          nil,
			secretGeneratorArgs: make([]string, 0),
			expectedError:       false,
		},
		{
			name:                "Generate a registration file",
			namespace:           "create-secret",
			secretName:          "test-appservice-registration",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"app.kubernetes.io/name": "test-secret"},
			secretKeys:          []string{"registration.yaml"},
			secretType:          Registration,
			secretData:          nil,
			secretGeneratorArgs: []string{"testdata/registration.yaml"},
			expectedError:       false,
		},
		{
			name:                "Secret exists with data",
			namespace:           "secret-exists",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"element.io/name": "secret-exists"},
			secretName:          "test-secret",
			secretKeys:          []string{"key2"},
			secretType:          Rand32,
			secretData:          map[string][]byte{"key1": []byte("dmFsdWUx")},
			secretGeneratorArgs: make([]string, 0),
			expectedError:       false,
		},
		{
			name:                "Secret exists and we don't override key",
			namespace:           "override-key",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"test-name": "override-key"},
			secretName:          "test-secret",
			secretKeys:          []string{"key2"},
			secretType:          Rand32,
			secretData:          map[string][]byte{"key2": []byte("dmFsdWUx")},
			secretGeneratorArgs: make([]string, 0),
			expectedError:       false,
		},
		{
			name:                "Secret exists but is not managed by matrix-tools-init-secrets",
			namespace:           "override-key",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"test-name": "override-key"},
			secretName:          "test-secret",
			secretKeys:          []string{"key2"},
			secretType:          Rand32,
			secretData:          map[string][]byte{"key2": []byte("dmFsdWUx")},
			secretGeneratorArgs: make([]string, 0),
			expectedError:       true,
		},
		{
			name:                "Create empty secret",
			namespace:           "empty-secret",
			initLabels:          map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:        map[string]string{"test-name": "override-key"},
			secretName:          "test-secret",
			secretKeys:          []string{},
			secretType:          Rand32,
			secretData:          nil,
			secretGeneratorArgs: make([]string, 0),
			expectedError:       false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			client := testclient.NewClientset()
			// Create a namespace
			_, err := client.CoreV1().Namespaces().Create(context.Background(), &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: tc.namespace}}, metav1.CreateOptions{})
			if err != nil {
				t.Fatalf("Failed to create namespace: %v", err)
			}
			secretsClient := client.CoreV1().Secrets(tc.namespace)
			// Create a secret with data
			if tc.secretData != nil {
				_, err := secretsClient.Create(context.Background(), &corev1.Secret{
					ObjectMeta: metav1.ObjectMeta{
						Name:      tc.secretName,
						Namespace: tc.namespace,
						Labels:    tc.initLabels,
					}, Data: tc.secretData}, metav1.CreateOptions{},
				)
				if err != nil {
					t.Fatalf("Failed to create secret: %v", err)
				}
			}

			for _, secretKey := range tc.secretKeys {
				existingSecretValue, valueExistsBeforeGen := tc.secretData[secretKey]
				err = GenerateSecret(client, tc.secretLabels, tc.namespace, tc.secretName, secretKey, tc.secretType, tc.secretGeneratorArgs)
				if err == nil && tc.expectedError {
					t.Fatalf("GenerateSecret() error is nil, expected an error")
				} else if err != nil && !tc.expectedError {
					t.Fatalf("GenerateSecret() error = %v, want nil", err)
				}
				// Check if the secret was created successfully
				secret, err := secretsClient.Get(context.Background(), tc.secretName, metav1.GetOptions{})
				if err != nil {
					t.Fatalf("Failed to get secret: %v", err)
				}

				if value, ok := secret.Data[secretKey]; ok {
					if valueExistsBeforeGen {
						existingSecretValueBytes := []byte(existingSecretValue)
						if !reflect.DeepEqual(value, existingSecretValueBytes) {
							t.Fatalf("The secret has been updated with the new value but it should not overwrite: %s", string(value))
						}
					} else {
						switch tc.secretType {
						case Rand32:
							if len(string(value)) != 32 {
								t.Fatalf("Unexpected data in secret: %v", value)
							}
						case SigningKey:
							expectedPattern := "ed25519 0 [a-zA-Z0-9]+"
							keyString := string(value)
							if !regexp.MustCompile(expectedPattern).MatchString(keyString) {
								t.Fatalf("Unexpected key format: %v", keyString)
							}
						case Registration:
							data := make(map[string]any)
							if err := yaml.Unmarshal(value, &data); err != nil {
								t.Fatalf("Unexpected data: %v", data)
							}
							if data["static"].(string) != "values" {
								t.Fatalf("Unexpected data, 'static' key should be 'values', found %v", data)
							}
							if len(data["as_token"].(string)) != 32 {
								t.Fatalf("Unexpected data,  as_token should be a random 32 bytes string, found %v", data)
							}
							if len(data["hs_token"].(string)) != 32 {
								t.Fatalf("Unexpected data,  as_token should be a random 32 bytes string, found %v", data)
							}
						}
					}
				} else {
					t.Errorf("Expected key to be set in the secret")
				}

				labels := secret.Labels
				if tc.secretData == nil {
					if !reflect.DeepEqual(labels, tc.secretLabels) {
						t.Fatalf("The secret has been created without the labels: %v", labels)
					}
				} else if tc.initLabels["app.kubernetes.io/managed-by"] == "matrix-tools-init-secrets" {
					if !reflect.DeepEqual(labels, tc.secretLabels) {
						t.Fatalf("The secret has not been updated with the new labels: %v", labels)
					}
				}
			}

		})
	}
}
