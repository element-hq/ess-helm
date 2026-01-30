// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package renderer

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"text/template"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Data map[string]any `json:"data"`
}

func deepMergeMaps(source, destination map[string]any, arrayOverwriteKeys []string) error {
	for key, value := range source {
		if destValue, exists := destination[key]; exists {
			if srcMap, ok := value.(map[string]any); ok {
				if destMap, ok := destValue.(map[string]any); ok {
					if err := deepMergeMaps(srcMap, destMap, nil); err != nil {
						return fmt.Errorf("failed to deep merge maps for key '%s': %w", key, err)
					}
				} else {
					destination[key] = value
				}
			} else if srcArray, ok := value.([]any); ok {
				if destArray, ok := destValue.([]any); ok {
					if arrayOverwriteKeys != nil && slices.Contains(arrayOverwriteKeys, key) {
						destination[key] = srcArray
					} else {
						destination[key] = append(destArray, srcArray...)
					}
				} else {
					destination[key] = srcArray
				}
			} else {
				destination[key] = value
			}
		} else {
			destination[key] = value
		}
	}
	return nil
}

func readfile(path string) (string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %w", err)
	}
	return string(content), nil
}

func replace(old, new, src string) string {
	return strings.ReplaceAll(src, old, new)
}

func quote(src string) string {
	return strconv.Quote(src)
}

func indent(i int, src string) string {
	return strings.Join(strings.Split(src, "\n"), "\n"+strings.Repeat(" ", i))
}

func urlencode(src string) string {
	return url.QueryEscape(src)
}

// RenderConfig takes a list of io.Reader objects representing yaml configuration files
// and returns a single map[string]any containing the deeply merged data as yaml format
// The files are merged in the order they are provided.
// Each file can contain variables to replace with the format ${VARNAME}
// Variables to replace are fetched from the environment variables. Their value
// is parsed through go template engine.
// 3 functions are available in the template :
// - readfile(path) : reads a file and returns its content
// - hostname() : returns the current host name
// - replace(old,new,string) : replaces old with new in string
// It also takes a list of strings that are expected to be top-level keys of arrays in one of more of the source configs
// If these are present these arrays are overwritten by later source configs rather than the default behaviour of appending
// These only impact the top-level keys and not anything nested
func RenderConfig(sourceConfigs []io.Reader, arrayOverwriteKeys []string) (map[string]any, error) {
	output := make(map[string]any)

	for _, configReader := range sourceConfigs {
		fileContent, err := io.ReadAll(configReader)
		if err != nil {
			return nil, errors.New("failed to read from reader: " + err.Error())
		}

		funcMap := template.FuncMap{
			"readfile":  readfile,
			"hostname":  os.Hostname,
			"replace":   replace,
			"quote":     quote,
			"urlencode": urlencode,
			"indent":    indent,
		}

		envVarNames := extractEnvVarNames(string(fileContent))
		for _, envVar := range envVarNames {
			val, ok := os.LookupEnv(envVar)
			if !ok {
				return nil, errors.New(envVar + " is not present in the environment")
			}
			var replacementValue []byte
			tmpl, err := template.New("matrix-tools").Funcs(funcMap).Parse(val)
			if err != nil {
				return nil, fmt.Errorf("failed to parse template for env var %s: %w", envVar, err)
			}
			var buffer bytes.Buffer
			err = tmpl.Execute(&buffer, output)
			if err != nil {
				return nil, fmt.Errorf("failed to render template for env var %s: %w", envVar, err)
			}
			replacementValue = buffer.Bytes()
			fileContent = bytes.ReplaceAll(fileContent, []byte("${"+envVar+"}"), replacementValue)
		}

		var data map[string]any
		if err := yaml.Unmarshal(fileContent, &data); err != nil {
			if os.Getenv("DEBUG_RENDERING") == "1" {
				fmt.Println(string(fileContent))
			}
			return nil, fmt.Errorf("post-processed yaml is invalid: %v", err)
		}

		if err := deepMergeMaps(data, output, arrayOverwriteKeys); err != nil {
			return nil, fmt.Errorf("failed to deep merge files %w", err)
		}
	}

	return output, nil
}

func extractEnvVarNames(fileContent string) []string {
	var envVars []string
	re := regexp.MustCompile(`\$\{([^\}]+)\}`)
	matches := re.FindAllStringSubmatch(fileContent, -1)
	for _, match := range matches {
		if len(match) > 1 {
			envVars = append(envVars, match[1])
		}
	}
	return envVars
}
