// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package renderer

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"reflect"
	"testing"
)

func TestRenderConfig(t *testing.T) {
	hostname, _ := os.Hostname()
	droppedFromHostname := hostname[2:4]

	testCases := []struct {
		name               string
		readers            []io.Reader
		env                map[string]string
		expected           map[string]any
		err                bool
		arrayOverwriteKeys []string
	}{
		{
			name: "Single File",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`key: ${TEST_ENV}
quotedValue: ${SPECIAL_CHARS}
secretKey: ${SECRET_KEY}
hostname: ${THIS_HOSTNAME}`)),
			},
			env: map[string]string{
				"TEST_ENV":      "value",
				"SPECIAL_CHARS": "{{ \"!ayamltype\" | quote }}",
				"SECRET_KEY":    "{{ readfile \"testdata/secret_key\" }}",
				"THIS_HOSTNAME": fmt.Sprintf("{{ hostname | replace \"%s\" \"\" }}", droppedFromHostname),
			},
			expected: map[string]any{
				"key":         "value",
				"secretKey":   "secret_value",
				"quotedValue": "!ayamltype",
				"hostname":    hostname[0:2] + hostname[4:],
			},
			err: false,
		},
		{
			name: "Multiple Files",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`key_1: value1
keyWithEnv1:
  env1: ${TEST_ENV_1}`)),
				bytes.NewBuffer([]byte(`key2: value2
keyWithEnv2:
  content_with_env2: ${TEST_ENV_2}`)),
			},
			env: map[string]string{
				"TEST_ENV_1": "env_value_1",
				"TEST_ENV_2": "env_value_2",
			},
			expected: map[string]any{
				"key_1": "value1",
				"key2":  "value2",
				"keyWithEnv1": map[string]any{
					"env1": "env_value_1",
				},
				"keyWithEnv2": map[string]any{
					"content_with_env2": "env_value_2",
				},
			},
			err: false,
		},
		{
			name: "Overrides in order",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`overriddenKey: value_000
mergedArray:
  - item_000_a
  - item_000_b
overriddenArray:
  - item_002_a
  - item_002_b
overriddenObject:
  childKey: value_000
only000Key: only_000`)),
				bytes.NewBuffer([]byte(`overriddenKey: value_001
mergedArray:
  - item_001_a
  - item_001_b
overriddenArray:
  - item_003_a
  - item_003_b
overriddenObject:
  childKey: value_001
only001Key: only_001`)),
			},
			expected: map[string]any{
				"overriddenKey": "value_001",
				"mergedArray": []any{
					"item_000_a",
					"item_000_b",
					"item_001_a",
					"item_001_b",
				},
				"overriddenArray": []any{
					"item_003_a",
					"item_003_b",
				},
				"overriddenObject": map[string]any{
					"childKey": "value_001",
				},
				"only000Key": "only_000",
				"only001Key": "only_001",
			},
			err:                false,
			arrayOverwriteKeys: []string{"overriddenArray"},
		},
		{
			name: "Environment Variable Missing",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`key: ${TEST_ENV}`)),
			},
			expected: nil,
			err:      true,
		},
		{
			name: "Indent Function Test",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`
key:
  indentedValue: |
    ${INDENTED_KEY}
anotherKey:
  value`)),
			},
			env: map[string]string{
				"INDENTED_KEY": "{{ readfile \"testdata/multiline\" | indent 4 }}",
			},
			expected: map[string]any{
				"key": map[string]interface{}{
					"indentedValue": "Line 1\n  Line 2\nLine 3\n",
				},
				"anotherKey": "value",
			},
			err: false,
		},
		{
			name: "UrlEncode Function Test",
			readers: []io.Reader{
				bytes.NewBuffer([]byte(`key: ${ENCODED_KEY}`)),
			},
			env: map[string]string{
				"ENCODED_KEY": "{{ urlencode \"Hello, World!\" }}",
			},
			expected: map[string]any{
				"key": "Hello%2C+World%21",
			},
			err: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			for k, v := range tc.env {
				if err := os.Setenv(k, v); err != nil {
					t.Errorf("Failed to set environment variable %s: %v", k, err)
				}
			}

			result, err := RenderConfig(tc.readers, tc.arrayOverwriteKeys)
			if (err != nil) != tc.err {
				t.Errorf("expected error: %v, got: %v", tc.err, err)
			}
			if !tc.err && !reflect.DeepEqual(result, tc.expected) {
				t.Errorf("expected: %v, got: %v", tc.expected, result)
			}
			for k := range tc.env {
				if err := os.Unsetenv(k); err != nil {
					t.Errorf("Failed to unset environment variable %s: %v", k, err)
				}
			}
		})
	}
}
