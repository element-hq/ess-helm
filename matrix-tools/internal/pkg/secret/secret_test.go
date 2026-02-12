// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"context"
	"reflect"
	"regexp"
	"testing"

	"go.yaml.in/yaml/v2"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	testclient "k8s.io/client-go/kubernetes/fake"
)

func TestGenerateSecret(t *testing.T) {
	testCases := []struct {
		name                  string
		namespace             string
		initLabels            map[string]string
		secretLabels          map[string]string
		generatedSecretsTypes map[string]SecretType
		secretName            string
		secretKeys            []string
		secretType            SecretType
		secretData            map[string][]byte
		expectedError         bool
		expectedChange        bool
	}{
		{
			name:                  "Create a new secret",
			namespace:             "create-secret",
			secretName:            "test-secret",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"app.kubernetes.io/name": "test-secret"},
			generatedSecretsTypes: map[string]SecretType{"key": Rand32},
			secretKeys:            []string{"key"},
			secretType:            Rand32,
			secretData:            nil,
			expectedError:         false,
			expectedChange:        true,
		},
		{
			name:                  "Create a new signing key",
			namespace:             "create-secret",
			secretName:            "test-signing-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"app.kubernetes.io/name": "test-secret"},
			generatedSecretsTypes: map[string]SecretType{"key": SigningKey},
			secretKeys:            []string{"key"},
			secretType:            SigningKey,
			secretData:            nil,
			expectedError:         false,
			expectedChange:        true,
		},
		{name: "Override wrong new signing key",
			namespace:             "create-secret",
			secretName:            "test-signing-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"app.kubernetes.io/name": "test-secret"},
			generatedSecretsTypes: map[string]SecretType{"key": SigningKey},
			secretKeys:            []string{"key"},
			secretType:            SigningKey,
			secretData:            map[string][]byte{"key": []byte("ed25519 0 Ng6VNhsOd/fWeMqIJ7+x9W+cpxzdIdnCER+QFC/Jt6w")},
			expectedError:         false,
			expectedChange:        true,
		},
		{
			name:                  "Secret exists with data",
			namespace:             "secret-exists",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"element.io/name": "secret-exists"},
			generatedSecretsTypes: map[string]SecretType{"key2": Rand32},
			secretName:            "test-secret",
			secretKeys:            []string{"key2"},
			secretType:            Rand32,
			secretData:            map[string][]byte{"key1": []byte("dmFsdWUx")},
			expectedError:         false,
			expectedChange:        true,
		},
		{
			name:                  "Secret exists and we don't override key",
			namespace:             "override-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"test-name": "override-key"},
			generatedSecretsTypes: map[string]SecretType{"key2": Rand32},
			secretName:            "test-secret",
			secretKeys:            []string{"key2"},
			secretType:            Rand32,
			secretData:            map[string][]byte{"key2": []byte("dmFsdWUx")},
			expectedError:         false,
			expectedChange:        false,
		},
		{
			name:                  "Secret exists but is not managed by matrix-tools-init-secrets",
			namespace:             "override-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"test-name": "override-key"},
			generatedSecretsTypes: map[string]SecretType{"key2": Rand32},
			secretName:            "test-secret",
			secretKeys:            []string{"key2"},
			secretType:            Rand32,
			secretData:            map[string][]byte{"key2": []byte("dmFsdWUx")},
			expectedError:         true,
			expectedChange:        false,
		},
		{
			name:                  "Create empty secret",
			namespace:             "empty-secret",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"test-name": "override-key"},
			generatedSecretsTypes: map[string]SecretType{},
			secretName:            "test-secret",
			secretKeys:            []string{},
			secretType:            Rand32,
			secretData:            nil,
			expectedError:         false,
			expectedChange:        true,
		}, {
			name:                  "Does not rotate existing signing key if key id 1",
			namespace:             "with-signing-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"test-name": "override-key"},
			secretName:            "test-secret",
			generatedSecretsTypes: map[string]SecretType{"SOME_SIGNING_KEY": SigningKey},
			secretKeys:            []string{},
			secretType:            ExpireKey,
			// Data with good signing key to not rotate
			secretData:     map[string][]byte{"SOME_SIGNING_KEY": []byte("ed25519 1 oy11WZaJNEyJbj+I27RlIXhz7JmDsT24yBz0QdvZ4K0")},
			expectedError:  false,
			expectedChange: false,
		},
		{name: "Does rotate existing signing key if key id 0",
			namespace:             "with-signing-key",
			initLabels:            map[string]string{"app.kubernetes.io/managed-by": "helm", "app.kubernetes.io/name": "create-secret"},
			secretLabels:          map[string]string{"test-name": "override-key"},
			secretName:            "test-secret",
			generatedSecretsTypes: map[string]SecretType{"SOME_SIGNING_KEY": SigningKey},
			secretKeys:            []string{},
			secretType:            ExpireKey,
			// Data with bad signing key id to rotate
			secretData:     map[string][]byte{"SOME_SIGNING_KEY": []byte("ed25519 0 Ozi/KgL1WiuGMmp/GUME26bMWtqH92jF036tK6SIks4")},
			expectedError:  false,
			expectedChange: true,
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
				err = GenerateSecret(client, tc.secretLabels, tc.generatedSecretsTypes, tc.namespace, tc.secretName, secretKey, tc.secretType)
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
						if tc.expectedChange && reflect.DeepEqual(value, existingSecretValue) {
							t.Fatalf("The secret has not been updated with the new value but the wrong signing key should overwrite: %s", string(value))
						}
						if !tc.expectedChange && !reflect.DeepEqual(value, existingSecretValue) {
							t.Fatalf("The secret has been updated with the new value but it should not overwrite: %s", string(value))
						}
					} else {
						switch tc.secretType {
						case Rand32:
							if len(string(value)) != 32 {
								t.Fatalf("Unexpected data in secret: %v", value)
							}
						case SigningKey:
							expectedPattern := "ed25519 1 ([a-zA-Z0-9\\/\\+]+)"
							keyString := string(value)
							if !regexp.MustCompile(expectedPattern).MatchString(keyString) {
								t.Fatalf("Unexpected key format: %v", keyString)
							}

						case ExpireKey:
							data := make(map[string]any)
							if err := yaml.Unmarshal(value, &data); err != nil {
								t.Fatalf("Unexpected data: %v", data)
							}
							old_signing_keys := data["old_signing_keys"].(map[string]map[string]map[string]string)
							if mustBeRotated(tc.secretData, "SOME_SIGNING_KEY") {
								if len(old_signing_keys) != 0 {
									t.Fatalf("Unexpected data,  old_signing_keys should be a empty, found %v", data)
								}
							} else {
								if _, ok := old_signing_keys["ed25519:0"]; !ok {
									t.Fatalf("Unexpected data,  old_signing_keys should be have the old bad key, found %v", data)
								}
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
