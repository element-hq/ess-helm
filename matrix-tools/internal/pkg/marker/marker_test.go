// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package marker

import (
	"context"
	"reflect"
	"testing"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	testclient "k8s.io/client-go/kubernetes/fake"
)

func TestGenerateConfigMap(t *testing.T) {
	testCases := []struct {
		name          string
		namespace     string
		initLabels    map[string]string
		labels        map[string]string
		configMapName string
		configMapKeys []string
		configMapData map[string]string
		step          string
		newValue      string
		allowedValues []string
		expectedError bool
	}{
		{
			name:          "Create a new marker (pre)",
			namespace:     "create-marker",
			configMapName: "test-marker-key",
			initLabels:    map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers", "app.kubernetes.io/name": "create-configMap"},
			labels:        map[string]string{"app.kubernetes.io/name": "test-configMap"},
			configMapKeys: []string{"key"},
			configMapData: nil,
			step:          "pre",
			newValue:      "valueA",
			allowedValues: []string{"valueA", "valueB"},
			expectedError: false,
		},
		{
			name:          "Create a new marker (post)",
			namespace:     "create-marker",
			configMapName: "test-marker-key",
			initLabels:    map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers", "app.kubernetes.io/name": "create-configMap"},
			labels:        map[string]string{"app.kubernetes.io/name": "test-configmap"},
			configMapKeys: []string{"key"},
			configMapData: nil,
			step:          "post",
			newValue:      "valueB",
			allowedValues: []string{"valueA", "valueB"},
			expectedError: false,
		},
		{
			name:          "Marker exists with invalid current value",
			namespace:     "marker-exists-invalid",
			initLabels:    map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers", "app.kubernetes.io/name": "create-configMap"},
			labels:        map[string]string{"element.io/name": "configmap-exists"},
			configMapName: "test-marker",
			configMapKeys: []string{"markerA"},
			configMapData: map[string]string{"markerA": "rawDeployment"},
			step:          "pre",
			newValue:      "additionalComponentEnabled",
			allowedValues: []string{"additionalComponentEnabled", "migrateFirst"},
			expectedError: true,
		},
		{
			name:          "Marker exists with valid current value (pre)",
			namespace:     "marker-exists-valid",
			initLabels:    map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers", "app.kubernetes.io/name": "create-configMap"},
			labels:        map[string]string{"element.io/name": "configmap-exists"},
			configMapName: "test-marker",
			configMapKeys: []string{"markerA"},
			configMapData: map[string]string{"markerA": "migrateFirst"},
			step:          "post",
			newValue:      "additionalComponentEnabled",
			allowedValues: []string{"additionalComponentEnabled", "migrateFirst"},
			expectedError: false,
		},
		{
			name:          "Marker exists with valid current value (post)",
			namespace:     "marker-exists-valid",
			initLabels:    map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers", "app.kubernetes.io/name": "create-configMap"},
			labels:        map[string]string{"element.io/name": "configmap-exists"},
			configMapName: "test-marker",
			configMapKeys: []string{"markerA"},
			configMapData: map[string]string{"markerA": "migrateFirst"},
			step:          "post",
			newValue:      "additionalComponentEnabled",
			expectedError: false,
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
			configMapClient := client.CoreV1().ConfigMaps(tc.namespace)
			// Create a configMap with data
			if tc.configMapData != nil {
				_, err := configMapClient.Create(context.Background(), &corev1.ConfigMap{
					ObjectMeta: metav1.ObjectMeta{
						Name:      tc.configMapName,
						Namespace: tc.namespace,
						Labels:    tc.initLabels,
					}, Data: tc.configMapData}, metav1.CreateOptions{},
				)
				if err != nil {
					t.Fatalf("Failed to create configMap: %v", err)
				}
			}

			for _, key := range tc.configMapKeys {
				exitingValue, valueExistsBeforeGen := tc.configMapData[key]
				err = GenerateConfigMap(client, tc.labels, tc.namespace, tc.configMapName, key, tc.step, tc.newValue, tc.allowedValues)
				if err == nil && tc.expectedError {
					t.Fatalf("GenerateConfigMap() error is nil, expected an error")
				} else if err != nil && !tc.expectedError {
					t.Fatalf("GenerateConfigMap() error = %v, want nil", err)
				}
				// Check if the configMap was created successfully
				configMap, err := configMapClient.Get(context.Background(), tc.configMapName, metav1.GetOptions{})
				if err != nil {
					t.Fatalf("Failed to get configMap: %v", err)
				}

				if value, ok := configMap.Data[key]; ok {
					if valueExistsBeforeGen {
						if tc.expectedError {
							if !reflect.DeepEqual(value, exitingValue) {
								t.Fatalf("The configMap has been updated with the new value but it should not overwrite: %s", string(value))
							}
						} else {
							switch tc.step {
							case "pre":
								if !reflect.DeepEqual(value, tc.configMapData[key]) {
									t.Fatalf("The configMap has been updated with the new value but it should not overwrite during pre step: %s", string(value))
								}
							case "post":
								if !reflect.DeepEqual(value, tc.newValue) {
									t.Fatalf("The configMap has not been updated with the new value but it should overwrite during post step: %s", string(value))
								}
							}
						}
					} else if !ok {
						t.Errorf("Expected key to be set in the configMap")
					}

					labels := configMap.Labels
					if !tc.expectedError {
						if tc.configMapData == nil {
							if !reflect.DeepEqual(labels, tc.labels) {
								t.Fatalf("The configMap has been created without the labels: %v", labels)
							}
						} else if tc.initLabels["app.kubernetes.io/managed-by"] == "matrix-tools-deployment-markers" {
							if !reflect.DeepEqual(labels, tc.labels) {
								t.Fatalf("The configMap has not been updated with the new labels: %v", labels)
							}
						}
					}
				}
			}
		})
	}
}
