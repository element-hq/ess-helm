// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
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
	SynapseConfig string
	MASConfig     string
}

func ParseArgs(args []string) (*Syn2MasOptions, error) {
	var options Syn2MasOptions

	syn2MasSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	masConfig := syn2MasSet.String("config", "", "Path to MAS config file")
	synapseConfig := syn2MasSet.String("synapse-config", "", "Path to Synapse config file")
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
	return &options, nil
}
