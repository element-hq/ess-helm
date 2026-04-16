// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import (
	"fmt"
	"os"
	"strings"

	executor "github.com/element-hq/ess-helm/matrix-tools/internal/pkg/tcpwait"
)

func Run(options *TcpWaitOptions) {
	address := options.Address
	if options.AddressFile != "" {
		hostBytes, err := os.ReadFile(options.AddressFile)
		if err != nil {
			fmt.Println("Failed to read address file:", err)
			os.Exit(1)
		}
		address = strings.TrimSpace(string(hostBytes)) + ":" + options.Port
	}
	executor.WaitForTCP(address)
}
