// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package main

import (
	"fmt"
	"os"

	deploymentmarkers "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/deployment-markers"
	generatesecrets "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/generate-secrets"
	renderconfig "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/render-config"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/syn2mas"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/tcpwait"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/args"
)

func main() {
	options, err := args.ParseArgs(os.Args)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	switch options.Command {
	case args.RenderConfig:
		renderconfig.Run(options.RenderConfig)
	case args.TCPWait:
		tcpwait.Run(options.TcpWait)
	case args.Syn2Mas:
		syn2mas.Run(options.Syn2Mas)
	case args.GenerateSecrets:
		generatesecrets.Run(options.GenerateSecrets)
	case args.DeploymentMarkers:
		deploymentmarkers.Run(options.DeploymentMarkers)
	default:
		fmt.Printf("Unknown command")
		os.Exit(1)
	}
}
