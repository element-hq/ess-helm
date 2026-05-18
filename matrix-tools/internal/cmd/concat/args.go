// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package concat

import (
	"flag"
	"fmt"
	"strings"
)

const (
	FlagSetName = "concat"
)

type ConcatOptions struct {
	Files  []string
	Output string
}

func ParseArgs(args []string) (*ConcatOptions, error) {
	options := &ConcatOptions{}

	concatSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	concatTarget := concatSet.String("target", "", "file to append to or create")

	err := concatSet.Parse(args)
	if err != nil {
		return nil, err
	}
	for _, file := range concatSet.Args() {
		if strings.HasPrefix(file, "-") {
			return nil, flag.ErrHelp
		}
		options.Files = append(options.Files, file)
	}
	options.Output = *concatTarget
	if *concatTarget == "" {
		return nil, fmt.Errorf("target file is required")
	}
	return options, nil
}
