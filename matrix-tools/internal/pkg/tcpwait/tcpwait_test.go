// Copyright 2025 New Vector Ltd
// Copyright 2025 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import (
	"fmt"
	"net"
	"testing"
)

// TestTCPWait tests that the tcpwait function correctly waits for a TCP connection.
func TestTCPWait(t *testing.T) {
	// Start a local TCP server in a goroutine
	listener, err := net.Listen("tcp", "localhost:0")
	if err != nil {
		t.Fatalf("Failed to start listener: %v", err)
	}
	defer func() {
		if err = listener.Close(); err != nil {
			t.Fatalf("Failed to close listener: %v", err)
		}
	}()

	// Get the address of the local TCP server
	serverAddr := listener.Addr().String()

	// Start a goroutine to handle incoming connections and close them immediately
	go func() {
		conn, err := listener.Accept()
		if err != nil {
			t.Errorf("Accept error: %v", err)
			return
		}
		defer func() {
			if err = conn.Close(); err != nil {
				fmt.Printf("Close error: %v", err)
			}
		}()
	}()

	// Call the tcpwait function with the server address and timeout
	WaitForTCP(serverAddr)
}
