// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package renderconfig

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/renderer"
	yaml "gopkg.in/yaml.v3"
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

func Run(options *RenderConfigOptions) {
	// If output file already exists, delete it to avoid a permission error on writes
	if _, err := os.Stat(options.Output); err == nil {
		fmt.Printf("Output file %s already exists, deleting\n", options.Output)
		err := os.Remove(options.Output)
		if err != nil {
			fmt.Println("Error deleting file:", err)
			os.Exit(1)
		}
	}

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
	result, err := renderer.RenderConfig(fileReaders, options.ArrayOverwriteKeys)
	if err != nil {
		if err == flag.ErrHelp {
			flag.CommandLine.Usage()
		} else {
			fmt.Println("Error:", err)
		}
		os.Exit(1)
	}
	var outputYAML []byte
	if outputYAML, err = yaml.Marshal(result); err != nil {
		fmt.Println("Error marshalling merged config to YAML:", err)
		os.Exit(1)
	}

	fmt.Printf("Rendering config to file: %v\n", options.Output)
	if os.Getenv("DEBUG_RENDERING") == "1" {
		fmt.Println(string(outputYAML))
	}
	err = os.WriteFile(options.Output, outputYAML, 0440)
	if err != nil {
		fmt.Println("Error writing to file:", err)
		os.Exit(1)
	}
}
