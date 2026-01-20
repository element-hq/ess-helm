// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
)

func generateRegistration(templatePath string) ([]byte, error) {
	fileReader, err := os.Open(templatePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}

	fileContent, err := io.ReadAll(fileReader)
	if err != nil {
		return nil, errors.New("failed to read from reader: " + err.Error())
	}

	hsToken, err := generateRandomString(32)
	if err != nil {
		return nil, errors.New("failed to generate hs token: " + err.Error())
	}
	asToken, err := generateRandomString(32)
	if err != nil {
		return nil, errors.New("failed to generate as token: " + err.Error())
	}
	fileContent = bytes.ReplaceAll(fileContent, []byte("${AS_TOKEN}"), hsToken)
	fileContent = bytes.ReplaceAll(fileContent, []byte("${HS_TOKEN}"), asToken)

	return fileContent, nil
}
