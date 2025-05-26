// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import (
	"fmt"
	"net"
	"os"
	"time"
)

// WaitForTCP waits for a TCP connection on the specified address.
func WaitForTCP(address string) {
	for {
		fmt.Println("Waiting for TCP connection on " + address)
		conn, err := net.DialTimeout("tcp", address, 5*time.Second)
		if err != nil {
			time.Sleep(time.Second)
		} else {
			defer func() {
				if err = conn.Close(); err != nil {
					fmt.Println(err)
					os.Exit(1)
				}
			}()
			break
		}
	}
}
