// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package generatesecrets

import (
	"flag"
	"fmt"
	"strings"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/secret"
)

const (
	FlagSetName = "generate-secrets"
)

type GenerateSecretsOptions struct {
	GeneratedSecrets []GeneratedSecret
	Labels           map[string]string
}

type GeneratedSecret struct {
	ArgValue      string
	Name          string
	Key           string
	Type          secret.SecretType
	GeneratorArgs []string
}

func parseSecretType(value string) (secret.SecretType, error) {
	switch value {
	case "rand32":
		return secret.Rand32, nil
	case "signingkey":
		return secret.SigningKey, nil
	case "hex32":
		return secret.Hex32, nil
	case "rsa":
		return secret.RSA, nil
	case "ecdsaprime256v1":
		return secret.EcdsaPrime256v1, nil
	case "registration":
		return secret.Registration, nil
	default:
		return secret.UnknownSecretType, fmt.Errorf("unknown secret type: %s", value)
	}
}

func ParseArgs(args []string) (*GenerateSecretsOptions, error) {
	var options GenerateSecretsOptions

	generateSecretsSet := flag.NewFlagSet("generate-secrets", flag.ExitOnError)
	secrets := generateSecretsSet.String("secrets", "", "Comma-separated list of secrets to generate, in the format of `name:key:type:args if required`, where `type` is one of: rand32, signingkey, hex32, rsa:<bits>:<der or pem>, ecdsaprime256v1")
	secretsLabels := generateSecretsSet.String("labels", "", "Comma-separated list of labels for generated secrets, in the format of `key=value`")

	err := generateSecretsSet.Parse(args)
	if err != nil {
		return nil, err
	}
	for _, generatedSecretArg := range strings.Split(*secrets, ",") {
		parsedValue := strings.Split(generatedSecretArg, ":")
		if len(parsedValue) < 3 {
			return nil, fmt.Errorf("invalid generated secret format, expect <name:key:type:...>: %s", generatedSecretArg)
		}
		var parsedSecretType secret.SecretType
		if parsedSecretType, err = parseSecretType(parsedValue[2]); err != nil {
			return nil, fmt.Errorf("invalid secret type in %s : %v", generatedSecretArg, err)
		}
		generatorArgs := make([]string, 0)
		if len(parsedValue) > 3 {
			generatorArgs = parsedValue[3:]
		}

		generatedSecret := GeneratedSecret{ArgValue: generatedSecretArg, Name: parsedValue[0], Key: parsedValue[1], Type: parsedSecretType, GeneratorArgs: generatorArgs}
		options.GeneratedSecrets = append(options.GeneratedSecrets, generatedSecret)
	}
	options.Labels = make(map[string]string)
	if *secretsLabels != "" {
		for _, label := range strings.Split(*secretsLabels, ",") {
			parsedLabelValue := strings.Split(label, "=")
			options.Labels[parsedLabelValue[0]] = parsedLabelValue[1]
		}
	}
	options.Labels["app.kubernetes.io/managed-by"] = "matrix-tools-init-secrets"
	return &options, nil
}
