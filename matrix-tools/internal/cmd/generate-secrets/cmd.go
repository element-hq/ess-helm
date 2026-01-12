// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package generatesecrets

import (
	"fmt"
	"os"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/secret"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/util"
	"github.com/pkg/errors"
)

func Run(options *GenerateSecretsOptions) {
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

	for _, generatedSecret := range options.GeneratedSecrets {
		err := secret.GenerateSecret(clientset, options.Labels, namespace,
			generatedSecret.Name, generatedSecret.Key, generatedSecret.Type, generatedSecret.GeneratorArgs)
		if err != nil {
			wrappedErr := errors.Wrapf(err, "error generating secret: %s", generatedSecret.ArgValue)
			fmt.Println("Error:", wrappedErr)
			os.Exit(1)
		}
	}
}
