// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package args

import (
	"flag"

	deploymentmarkers "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/deployment-markers"
	generatesecrets "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/generate-secrets"
	renderconfig "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/render-config"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/syn2mas"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/tcpwait"
)

type CommandType int

const (
	RenderConfig CommandType = iota
	GenerateSecrets
	DeploymentMarkers
	Syn2Mas
	TCPWait
)


type Options struct {
	Command             CommandType
	RenderConfig        *renderconfig.RenderConfigOptions
	GenerateSecrets     *generatesecrets.GenerateSecretsOptions
	DeploymentMarkers     *deploymentmarkers.DeploymentMarkersOptions
	Syn2Mas             *syn2mas.Syn2MasOptions
	TcpWait             *tcpwait.TcpWaitOptions
}

func ParseArgs(args []string) (*Options, error) {
	var options Options

	switch args[1] {
	case renderconfig.FlagSetName:
		options.Command = RenderConfig
		render, err := renderconfig.ParseArgs(args[2:])
		if err != nil {
			return nil, err
		}
		options.RenderConfig = render
	case tcpwait.FlagSetName:
		options.Command = TCPWait
		tcpwait, err := tcpwait.ParseArgs(args[2:])
		if err != nil {
			return nil, err
		}
		options.TcpWait = tcpwait
	case syn2mas.FlagSetName:
		options.Command = Syn2Mas
		syn2masOptions, err := syn2mas.ParseArgs(args[2:])
		if err != nil {
			return nil, err
		}
		options.Syn2Mas = syn2masOptions
	case generatesecrets.FlagSetName:
		options.Command = GenerateSecrets
		generateSecretsOptions, err := generatesecrets.ParseArgs(args[2:])
		if err != nil {
			return nil, err
		}
		options.GenerateSecrets = generateSecretsOptions
	case deploymentmarkers.FlagSetName:
		options.Command = DeploymentMarkers
		deploymentMarkersOptions, err := deploymentmarkers.ParseArgs(args[2:])
		if err != nil {
			return nil, err
		}
		options.DeploymentMarkers = deploymentMarkersOptions
	default:
		return nil, flag.ErrHelp
	}

	return &options, nil
}
