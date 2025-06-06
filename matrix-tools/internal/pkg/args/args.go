// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package args

import (
	"flag"
	"fmt"
	"strings"
)

type CommandType int

const (
	RenderConfig CommandType = iota
	GenerateSecrets
	DeploymentMarkers
	Syn2Mas
	TCPWait
)

type SecretType int

const (
	UnknownSecretType SecretType = iota
	Rand32
	SigningKey
	Hex32
	RSA
	EcdsaPrime256v1
	EcdsaSecp256k1
	EcdsaSecp384r1
)

func parseSecretType(value string) (SecretType, error) {
	switch value {
	case "rand32":
		return Rand32, nil
	case "signingkey":
		return SigningKey, nil
	case "hex32":
		return Hex32, nil
	case "rsa":
		return RSA, nil
	case "ecdsaprime256v1":
		return EcdsaPrime256v1, nil
	case "ecdsasecp256k1":
		return EcdsaSecp256k1, nil
	default:
		return UnknownSecretType, fmt.Errorf("unknown secret type: %s", value)
	}
}

type GeneratedSecret struct {
	ArgValue      string
	Name          string
	Key           string
	Type          SecretType
}

type DeploymentMarker struct {
	Name          string
	Key           string
	Step          string
	NewValue      string
	AllowedValues []string
}

type Options struct {
	Command          CommandType
	Files            []string
	Output           string
	Debug            bool
	Address          string
	GeneratedSecrets []GeneratedSecret
	DeploymentMarkers []DeploymentMarker
	Labels     map[string]string
	SynapseConfig    string
	MASConfig        string
}

func ParseArgs(args []string) (*Options, error) {
	var options Options

	renderConfigSet := flag.NewFlagSet("render-config", flag.ExitOnError)
	output := renderConfigSet.String("output", "", "Output file for rendering")

	tcpWaitSet := flag.NewFlagSet("tcpwait", flag.ExitOnError)
	tcpWait := tcpWaitSet.String("address", "", "Address to listen on for TCP connections")

	syn2MasSet := flag.NewFlagSet("syn2mas", flag.ExitOnError)
	masConfig := syn2MasSet.String("config", "", "Path to MAS config file")
	synapseConfig := syn2MasSet.String("synapse-config", "", "Path to Synapse config file")

	generateSecretsSet := flag.NewFlagSet("generate-secrets", flag.ExitOnError)
	secrets := generateSecretsSet.String("secrets", "", "Comma-separated list of secrets to generate, in the format of `name:key:type`, where `type` is one of: rand32")
	secretsLabels := generateSecretsSet.String("labels", "", "Comma-separated list of labels for generated secrets, in the format of `key=value`")

	deploymentMarkersSet := flag.NewFlagSet("deployment-markers", flag.ExitOnError)
	deploymentMarkers := deploymentMarkersSet.String("markers", "", "Comma-separated list of deployment markers, with Semi-colon separated list of previous allowed values in the format of `name:step:newValue:[allowedValues;..]`")
	labels := deploymentMarkersSet.String("labels", "", "Comma-separated list of labels for generated secrets, in the format of `key=value`")
	step := deploymentMarkersSet.String("step", "", "One of `pre` or `post`")

	switch args[1] {
	case "render-config":
		err := renderConfigSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		for _, file := range renderConfigSet.Args() {
			if strings.HasPrefix(file, "-") {
				return nil, flag.ErrHelp
			}
			options.Files = append(options.Files, file)
		}
		options.Output = *output
		if *output == "" {
			return nil, fmt.Errorf("output file is required")
		}
		options.Command = RenderConfig
	case "tcpwait":
		err := tcpWaitSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		if *tcpWait != "" {
			options.Address = *tcpWait
		}
		options.Command = TCPWait
	case "syn2mas":
		err := syn2MasSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		if *masConfig != "" {
			options.MASConfig = *masConfig
		} else {
			return nil, fmt.Errorf("-config <file> is required")
		}
		if *synapseConfig != "" {
			options.SynapseConfig = *synapseConfig
		} else {
			return nil, fmt.Errorf("-synapse-config <file> is required")
		}
		options.Command = Syn2Mas
	case "generate-secrets":
		err := generateSecretsSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		for _, generatedSecretArg := range strings.Split(*secrets, ",") {
			parsedValue := strings.Split(generatedSecretArg, ":")
			if len(parsedValue) < 3 {
				return nil, fmt.Errorf("invalid generated secret format, expect <name:key:type:...>: %s", generatedSecretArg)
			}
			var parsedSecretType SecretType
			if parsedSecretType, err = parseSecretType(parsedValue[2]); err != nil {
				return nil, fmt.Errorf("invalid secret type in %s : %v", generatedSecretArg, err)
			}

			generatedSecret := GeneratedSecret{ArgValue: generatedSecretArg, Name: parsedValue[0], Key: parsedValue[1], Type: parsedSecretType}
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
		options.Command = GenerateSecrets
	case "deployment-markers":
		err := deploymentMarkersSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		for _, deploymentMarkerArg := range strings.Split(*deploymentMarkers, ",") {
			parsedValue := strings.Split(deploymentMarkerArg, ":")
			if len(parsedValue) < 3 {
				return nil, fmt.Errorf("invalid deployment marker format, expect <name:key:newValue:[allowedValues;..]>: %s", deploymentMarkerArg)
			}
			parsedAllowedValues := strings.Split(parsedValue[3], ";")
			deploymentMarker := DeploymentMarker{Name: parsedValue[0], Key: parsedValue[1], Step: *step, NewValue: parsedValue[2], AllowedValues: parsedAllowedValues}
			options.DeploymentMarkers = append(options.DeploymentMarkers, deploymentMarker)
			options.Command = DeploymentMarkers
			options.Labels = make(map[string]string)
			if *labels != "" {
				for _, label := range strings.Split(*labels, ",") {
					parsedLabelValue := strings.Split(label, "=")
					options.Labels[parsedLabelValue[0]] = parsedLabelValue[1]
				}
			}
			options.Labels["app.kubernetes.io/managed-by"] = "matrix-tools-deployment-markers"
		}
	default:
		return nil, flag.ErrHelp
	}

	return &options, nil
}
