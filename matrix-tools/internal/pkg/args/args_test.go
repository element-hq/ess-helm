// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package args

import (
	"reflect"
	"testing"
)

func TestParseArgs(t *testing.T) {
	testCases := []struct {
		name     string
		args     []string
		expected *Options
		err      bool
	}{
		{
			name:     "Invalid number of arguments",
			args:     []string{"cmd", "render-config"},
			expected: &Options{},
			err:      true,
		},
		{
			name: "Missing --output flag",
			args: []string{"cmd", "render-config", "file1"},
			expected: &Options{
				Files: []string{"file1"},
			},
			err: true,
		},
		{
			name:     "Invalid flag",
			args:     []string{"cmd", "render-config", "file1", "-invalidflag"},
			expected: &Options{},
			err:      true,
		},
		{
			name: "Multiple files and --output flag",
			args: []string{"cmd", "render-config", "-output", "outputFile", "file1", "file2"},
			expected: &Options{
				Files:  []string{"file1", "file2"},
				Output: "outputFile",
			},
			err: false,
		},
		{
			name: "Correct usage of render-config",
			args: []string{"cmd", "render-config", "-output", "outputFile", "file1", "file2"},
			expected: &Options{
				Files:   []string{"file1", "file2"},
				Output:  "outputFile",
				Command: RenderConfig,
			},
			err: false,
		},
		{
			name: "Correct usage of tcp-wait",
			args: []string{"cmd", "tcpwait", "-address", "address:port"},
			expected: &Options{
				Address: "address:port",
				Command: TCPWait,
			},
			err: false,
		},
		{
			name: "Correct usage of generate-secrets",
			args: []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:rand32", "-labels", "mykey=myval"},
			expected: &Options{
				GeneratedSecrets: []GeneratedSecret{
					{ArgValue: "secret1:value1:rand32", Name: "secret1", Key: "value1", Type: Rand32},
				},
				Labels: map[string]string{"mykey": "myval", "app.kubernetes.io/managed-by":"matrix-tools-init-secrets"},
				Command:      GenerateSecrets,
			},
			err: false,
		},

		{
			name: "Multiple generated secrets",
			args: []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:rand32,secret2:value2:signingkey"},
			expected: &Options{
				GeneratedSecrets: []GeneratedSecret{
					{ArgValue: "secret1:value1:rand32", Name: "secret1", Key: "value1", Type: Rand32},
					{ArgValue: "secret2:value2:signingkey", Name: "secret2", Key: "value2", Type: SigningKey},
				},
				Labels: map[string]string{"app.kubernetes.io/managed-by":"matrix-tools-init-secrets"},
				Command: GenerateSecrets,
			},
			err: false,
		},

		{
			name:     "Invalid secret type",
			args:     []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:unknown"},
			expected: &Options{},
			err:      true,
		},

		{
			name:     "Wrong syntax of deployment-markers",
			args:     []string{"cmd", "deployment-markers", "-markers", "value1:rand32"},
			expected: &Options{},
			err:      true,
		},
		{
			name: "Multiple deployment-markers",
			args: []string{"cmd", "deployment-markers", "-markers", "cm1:key1:pre:value1:value1,cm1:key2:pre:value2:value1;value2"},
			expected: &Options{
				DeploymentMarkers: []DeploymentMarker{
					{Name: "cm1", Key: "key1", Step: "pre", NewValue: "value1", AllowedValues: []string{"value1"}},
					{Name: "cm1", Key: "key2", Step: "pre", NewValue: "value2", AllowedValues: []string{"value1", "value2"}},
				},
				Command: DeploymentMarkers,
				Labels: map[string]string{"app.kubernetes.io/managed-by":"matrix-tools-deployment-markers"},
			},
			err: false,
		},

		{
			name:     "Invalid secret type",
			args:     []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:unknown"},
			expected: &Options{},
			err:      true,
		},

		{
			name:     "Wrong syntax of generated secret",
			args:     []string{"cmd", "generate-secrets", "-secrets", "value1:rand32"},
			expected: &Options{},
			err:      true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if options, err := ParseArgs(tc.args); (err != nil) != tc.err || (err == nil && !reflect.DeepEqual(options, tc.expected)) {
				t.Errorf("Expected %v with err %v, got %v with err: %v", tc.expected, tc.err, options, (err != nil))
			}
		})
	}
}
