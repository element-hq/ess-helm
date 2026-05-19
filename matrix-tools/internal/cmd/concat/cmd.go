// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package concat

import (
	"fmt"
	"io"
	"os"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/concat"
)

func readFiles(paths []string) ([]io.Reader, []func() error, error) {
	files := make([]io.Reader, 0)
	closeFiles := make([]func() error, 0)
	for _, path := range paths {
		fileReader, err := os.Open(path)
		if err != nil {
			return files, closeFiles, fmt.Errorf("failed to open file: %w", err)
		}
		files = append(files, fileReader)
		closeFiles = append(closeFiles, fileReader.Close)
	}
	return files, closeFiles, nil
}

func Run(options *ConcatOptions) {
	fileReaders, closeFiles, err := readFiles(options.Files)
	defer func() {
		for _, closeFn := range closeFiles {
			err := closeFn()
			if err != nil {
				fmt.Println("Error closing file : ", err)
			}
		}
	}()
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	err = concat.Concat(fileReaders, options.Output)
	if err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}

}
