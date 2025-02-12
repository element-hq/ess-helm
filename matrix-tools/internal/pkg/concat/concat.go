// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

package concat

import (
	"errors"
	"fmt"
	"io"
	"os"
)

// Concat takes a list of io.Reader objects representing source files
// and a path to a single target file, and appends each source file to the target file.
// If the target file does not exist, it will be created as an empty file before being appended to.
func Concat(sourceFiles []io.Reader, targetPath string) error {
	fileWriter, err := os.OpenFile(targetPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open file for writing: %w", err)
	}
	defer func() {
		err := fileWriter.Close()
		if err != nil {
			fmt.Println("Error closing file for writing :", err)
		}
	}()

	for _, fileReader := range sourceFiles {
		fileContent, err := io.ReadAll(fileReader)
		if err != nil {
			return errors.New("failed to read from reader: " + err.Error())
		}
		_, err = fileWriter.Write(fileContent)
		if err != nil {
			return errors.New("failed to write to writer: " + err.Error())
		}
	}
	return nil
}
