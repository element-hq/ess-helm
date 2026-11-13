// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package syn2mas

import (
	"flag"
	"fmt"
)

const (
	FlagSetName = "syn2mas"
)

type Syn2MasOptions struct {
	SynapseConfig  string
	MASConfig      string
	DryRun         bool
	AcceptWarnings bool
}

func ParseArgs(args []string) (*Syn2MasOptions, error) {
	var options Syn2MasOptions

	syn2MasSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	masConfig := syn2MasSet.String("config", "", "Path to MAS config file")
	synapseConfig := syn2MasSet.String("synapse-config", "", "Path to Synapse config file")
	dryRun := syn2MasSet.Bool("dry-run", false, "Whether this being run in dry-run mode or not")
	acceptWarnings := syn2MasSet.Bool("accept-warnings", false, "Whether to proceed when syn2mas check only reports warnings")
	err := syn2MasSet.Parse(args)
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
	options.DryRun = *dryRun
	options.AcceptWarnings = *acceptWarnings
	return &options, nil
}
