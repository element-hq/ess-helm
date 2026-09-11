// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
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

	currentMarkerState := os.Getenv("CURRENT_MARKER_STATE")
	// We don't need to consider the `delegated_auth`` state (i.e. after a deployment has happened with syn2mas has been turned off)
	// Because we don't allow transitioning back from `delegated_auth`` -> `syn2mas_migrated``
	// If deploymentMarkers is off then we won't have any record in cluster and we'll have the empty string here and migration will proceed
	if currentMarkerState == "syn2mas_migrated" {
		fmt.Println("The cluster is recording the syn2mas migration as already having occurred. Skipping the migration")
		os.Exit(0)
	}

	// Dry-run (and check) is always executed before doing a real migration
	executor.DryRunSyn2MAS(options.SynapseConfig, options.MASConfig)
	if !options.DryRun {
		executor.RunSyn2MAS(clientset, namespace, options.SynapseConfig, options.MASConfig)
	}
}
