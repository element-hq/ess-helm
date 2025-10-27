// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package deploymentmarkers

import (
	"fmt"
	"os"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/marker"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/util"
	"github.com/pkg/errors"
)

func Run(options *DeploymentMarkersOptions) {
	clientset, err := util.GetKubernetesClient()
	if err != nil {
		fmt.Println("Error getting Kubernetes client: ", err)
		os.Exit(1)
	}
	namespace := os.Getenv("NAMESPACE")
	if namespace == "" {
		fmt.Println("Error, $NAMESPACE is not defined")
		os.Exit(1)
	}

	for _, depMarker := range options.DeploymentMarkers {
		err := marker.GenerateConfigMap(clientset, options.Labels, namespace, depMarker.Name, depMarker.Key, depMarker.Step, depMarker.NewValue, depMarker.AllowedValues)
		if err != nil {
			wrappedErr := errors.Wrapf(err, "error generating configmap: %v", depMarker)
			fmt.Println("Error:", wrappedErr)
			os.Exit(1)
		}
	}
}
