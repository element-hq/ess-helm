// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import "flag"

const (
	FlagSetName = "tcpwait"
)

type TcpWaitOptions struct {
	Address     string
	AddressFile string
	Port        string
}

func ParseArgs(args []string) (*TcpWaitOptions, error) {
	var options TcpWaitOptions

	tcpWaitSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	address := tcpWaitSet.String("address", "", "Address (host:port) to wait on for TCP connections")
	addressFile := tcpWaitSet.String("address-file", "", "File containing host to wait on for TCP connections (use with -port)")
	port := tcpWaitSet.String("port", "", "Port to use with -address-file")

	err := tcpWaitSet.Parse(args)
	if err != nil {
		return nil, err
	}
	options.Address = *address
	options.AddressFile = *addressFile
	options.Port = *port
	return &options, nil
}
