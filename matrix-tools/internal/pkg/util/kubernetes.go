// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package util

import (
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)


func GetKubernetesClient() (kubernetes.Interface, error) {
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, err
	}
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}
	return clientset, nil
}
