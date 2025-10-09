// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package syn2mas

import (
	"fmt"
	"os"

	executor "github.com/element-hq/ess-helm/matrix-tools/internal/pkg/syn2mas"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/util"
)

func Run(options *Syn2MasOptions) {
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
	executor.RunSyn2MAS(clientset, namespace, options.SynapseConfig, options.MASConfig)
}
