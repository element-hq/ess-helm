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
	generatedSecretsTypes := make(map[string]secret.SecretType)
	for _, generatedSecret := range options.GeneratedSecrets {
		generatedSecretsTypes[generatedSecret.Key] = generatedSecret.Type
	}
	// Do a first pass to generate extra synapse config depending on the existing
	// signing keys
	for _, generatedSecret := range options.GeneratedSecrets {
		if generatedSecret.Type == secret.ExpireKey {
			err := secret.GenerateSecret(clientset, options.Labels, generatedSecretsTypes,
				namespace, generatedSecret.Name, generatedSecret.Key, generatedSecret.Type, generatedSecret.GeneratorArgs)
			if err != nil {
				wrappedErr := errors.Wrapf(err, "error generating secret: %s", generatedSecret.ArgValue)
				fmt.Println("Error:", wrappedErr)
				os.Exit(1)
			}
		}
	}

	// We do a second pass which will re-generate the signing key if it was invalid
	for _, generatedSecret := range options.GeneratedSecrets {
		if generatedSecret.Type == secret.ExpireKey {
			continue
		}
		err := secret.GenerateSecret(clientset, options.Labels, generatedSecretsTypes,
			namespace, generatedSecret.Name, generatedSecret.Key, generatedSecret.Type, generatedSecret.GeneratorArgs)
		if err != nil {
			wrappedErr := errors.Wrapf(err, "error generating secret: %s", generatedSecret.ArgValue)
			fmt.Println("Error:", wrappedErr)
			os.Exit(1)
		}
	}
}
