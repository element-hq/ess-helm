// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only
// internal/pkg/marker/marker.go

package marker

import (
	"context"
	"fmt"
	"strings"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func GenerateConfigMap(client kubernetes.Interface, labels map[string]string, namespace string, name string, key string, step string, newValue string, allowedValues []string) error {
	ctx := context.Background()

	configMapsClient := client.CoreV1().ConfigMaps(namespace)
	configMapMeta := metav1.ObjectMeta{
		Name:      name,
		Namespace: namespace,
		Labels:    labels,
	}
	// Fetch the existing configmap or initialize an empty one
	existingConfigMap, err := configMapsClient.Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		existingConfigMap, err = configMapsClient.Create(ctx, &corev1.ConfigMap{
			ObjectMeta: configMapMeta, Data: nil}, metav1.CreateOptions{},
		)
		if err != nil {
			return fmt.Errorf("failed to initialize configmap: %w", err)
		}
	} else {
		if managedBy, ok := existingConfigMap.Labels["app.kubernetes.io/managed-by"]; ok {
			if managedBy != "matrix-tools-deployment-markers" {
				return fmt.Errorf("configmap %s/%s is not managed by this matrix-tools-deployment-markers", namespace, name)
			}
		} else {
			return fmt.Errorf("configmap %s/%s is not managed by this matrix-tools-deployment-markers", namespace, name)
		}
		// Make sure the labels are set correctly
		existingConfigMap.Labels = labels
	}

	// Add or update the key in the data
	if existingConfigMap.Data == nil {
		existingConfigMap.Data = make(map[string]string)
	}

	currentValueIsAllowed := false
	switch step {
		case "pre":
			// During pre-install, we check if the current value is in the allowed values
			// If it is not, it means the state of the deployment will not support the helm upgrade
			// and the upgrade will fail
			if _, ok := existingConfigMap.Data[key]; ok {
				for _, allowed := range allowedValues {
					if string(existingConfigMap.Data[key]) == allowed {
						fmt.Printf("Existing value: %s", string(existingConfigMap.Data[key]))
						currentValueIsAllowed = true
						break
					}
				}
				if !currentValueIsAllowed {
					return fmt.Errorf("%s marker prevented transitioning to value %s from value %s because it is not in the allowed values : %s", key, newValue, string(existingConfigMap.Data[key]), strings.Join(allowedValues, ", "))
				}
			}
		case "post":
			// During post-install, we update the configmap with the new value as the upgrade succeeded
			existingConfigMap.Data[key] = newValue
		default:
			return fmt.Errorf("unknown step: %s", step)
		}

	_, err = configMapsClient.Update(ctx, existingConfigMap, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("failed to update configmap: %w", err)
	}
	fmt.Printf("Successfully updated configmap: %s:%s\n", name, key)
	return nil
}
