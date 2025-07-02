// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import "flag"

const (
	FlagSetName = "tcpwait"
)

type TcpWaitOptions struct {
	Address string
}

func ParseArgs(args []string) (*TcpWaitOptions, error) {
	var options TcpWaitOptions

	tcpWaitSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	address := tcpWaitSet.String("address", "", "Address to listen on for TCP connections")

	err := tcpWaitSet.Parse(args)
	if err != nil {
		return nil, err
	}
	options.Address = *address
	return &options, nil
}
