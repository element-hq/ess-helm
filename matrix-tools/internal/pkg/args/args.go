// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

package args

import (
	"flag"
	"fmt"
	"strings"
)

type SecretType int

const (
	UnknownSecretType SecretType = iota
	Rand32
)

func parseSecretType(value string) (SecretType, error) {
	switch value {
	case "rand32":
		return Rand32, nil
	default:
		return UnknownSecretType, fmt.Errorf("unknown secret type: %s", value)
	}
}

type GeneratedSecret struct {
	ArgValue string
	Name     string
	Key      string
	Type     SecretType
}

type Options struct {
	Files            []string
	Output           string
	Address          string
	GeneratedSecrets []GeneratedSecret
}

func ParseArgs(args []string) (*Options, error) {
	var options Options

	renderConfigSet := flag.NewFlagSet("render-config", flag.ExitOnError)
	output := renderConfigSet.String("output", "", "Output file for rendering")

	tcpWaitSet := flag.NewFlagSet("tcpwait", flag.ExitOnError)
	tcpWait := tcpWaitSet.String("address", "", "Address to listen on for TCP connections")

	generateSecretsSet := flag.NewFlagSet("generate-secrets", flag.ExitOnError)

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
	case "tcpwait":
		err := tcpWaitSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		if *tcpWait != "" {
			options.Address = *tcpWait
		}
	case "generate-secrets":
		err := generateSecretsSet.Parse(args[2:])
		if err != nil {
			return nil, err
		}
		for _, generatedSecretArg := range generateSecretsSet.Args() {
			parsedValue := strings.Split(generatedSecretArg, ":")
			if len(parsedValue) != 3 {
				return nil, fmt.Errorf("invalid generated secret format, expect <name:key:type>: %s", generatedSecretArg)
			}
			var parsedSecretType SecretType
			if parsedSecretType, err = parseSecretType(parsedValue[2]); err != nil {
				return nil, fmt.Errorf("invalid secret type in %s", generatedSecretArg)
			}

			generatedSecret := GeneratedSecret{ArgValue: generatedSecretArg, Name: parsedValue[0], Key: parsedValue[1], Type: parsedSecretType}
			options.GeneratedSecrets = append(options.GeneratedSecrets, generatedSecret)
		}
	default:
		return nil, flag.ErrHelp
	}

	return &options, nil
}
