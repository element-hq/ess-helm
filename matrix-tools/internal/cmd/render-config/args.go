// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
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
	Files              []string
	Output             string
	ArrayOverwriteKeys []string
}

func ParseArgs(args []string) (*RenderConfigOptions, error) {
	var options RenderConfigOptions

	renderConfigSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	output := renderConfigSet.String("output", "", "Output file for rendering")
	arrayOverwriteKeys := renderConfigSet.String("array-overwrite-keys", "", "Comma-separated list of top-level config keys, that are arrays and should overwrite any existing array in earlier files, rather than the default of appending to them")

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
	if *arrayOverwriteKeys != "" {
		options.ArrayOverwriteKeys = strings.Split(*arrayOverwriteKeys, ",")
	}
	options.Output = *output
	if *output == "" {
		return nil, fmt.Errorf("output file is required")
	}

	return &options, nil
}
