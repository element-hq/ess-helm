// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

package main

import (
	"fmt"
	"io"
	"os"

	"flag"

	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/args"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/concat"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/renderer"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/secret"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/tcpwait"
	"github.com/pkg/errors"
	"gopkg.in/yaml.v3"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

func getKubernetesClient() (kubernetes.Interface, error) {
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, err
	}
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}
	return clientset, nil
}

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

func main() {
	options, err := args.ParseArgs(os.Args)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	switch options.Command {
	case args.RenderConfig:
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
		result, err := renderer.RenderConfig(fileReaders)
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
		err = os.WriteFile(options.Output, outputYAML, 0644)
		if err != nil {
			fmt.Println("Error writing to file:", err)
			os.Exit(1)
		}
	case args.TCPWait:
		tcpwait.WaitForTCP(options.Address)
	case args.GenerateSecrets:
		clientset, err := getKubernetesClient()
		if err != nil {
			fmt.Println("Error getting Kubernetes client: ", err)
			os.Exit(1)
		}
		namespace := os.Getenv("NAMESPACE")
		if namespace == "" {
			fmt.Println("Error, $NAMESPACE is not defined")
			os.Exit(1)
		}

		for _, generatedSecret := range options.GeneratedSecrets {
			err := secret.GenerateSecret(clientset, options.SecretLabels, namespace, generatedSecret.Name, generatedSecret.Key, generatedSecret.Type)
			if err != nil {
				wrappedErr := errors.Wrapf(err, "error generating secret: %s", generatedSecret.ArgValue)
				fmt.Println("Error:", wrappedErr)
				os.Exit(1)
			}
		}
	case args.Concat:
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
	default:
		fmt.Printf("Unknown command")
		os.Exit(1)
	}
}
