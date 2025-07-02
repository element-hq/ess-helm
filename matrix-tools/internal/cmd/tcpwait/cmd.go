// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package tcpwait

import (
	executor "github.com/element-hq/ess-helm/matrix-tools/internal/pkg/tcpwait"
)

func Run(options *TcpWaitOptions) {
	executor.WaitForTCP(options.Address)
}
