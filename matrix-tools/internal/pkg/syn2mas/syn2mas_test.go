// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only
// internal/pkg/secret/secret.go

package syn2mas

import (
	"context"
	"reflect"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	testclient "k8s.io/client-go/kubernetes/fake"
)

func TestScaleDown(t *testing.T) {
	ctx := context.Background()
	namespace := "test"
	client := testclient.NewClientset()
	// Create a namespace
	_, err := client.CoreV1().Namespaces().Create(context.Background(), &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: namespace}}, metav1.CreateOptions{})
	if err != nil {
		t.Fatalf("Failed to create namespace: %v", err)
	}
	oneReplica := int32(1)
	_, err = client.AppsV1().StatefulSets(namespace).Create(ctx, &appsv1.StatefulSet{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "synapse",
			Namespace: namespace,
			Labels:    map[string]string{
				"app.kubernetes.io/name": "synapse",
			},
		},
		Spec: appsv1.StatefulSetSpec{
			Replicas: &oneReplica,
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"app": "synapse",
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"app": "synapse",
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "synapse",
							Image: "synapse:latest",
						},
					},
				},
			},
		},
	}, metav1.CreateOptions{})
	if err != nil {
		t.Fatalf("Failed to create StatefulSet: %v", err)
	}
	scaledSts := scaleDownSynapse(client, namespace)

	expectedSts := map[string]int32{"synapse": 1}
	if !reflect.DeepEqual(scaledSts, expectedSts) {
		t.Errorf("Expected %v, got %v", expectedSts, scaledSts)
	}
}
