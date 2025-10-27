// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package renderconfig

import (
	"flag"
	"fmt"
	"strings"
)

const (
	FlagSetName = "render-config"
)

type RenderConfigOptions struct {
	Files  []string
	Output string
}

func ParseArgs(args []string) (*RenderConfigOptions, error) {
	var options RenderConfigOptions

	renderConfigSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	output := renderConfigSet.String("output", "", "Output file for rendering")

	err := renderConfigSet.Parse(args)
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

	return &options, nil
}
