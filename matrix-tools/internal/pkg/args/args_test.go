// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package args

import (
	"testing"

	"github.com/stretchr/testify/assert"

	deploymentmarkers "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/deployment-markers"
	generatesecrets "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/generate-secrets"
	renderconfig "github.com/element-hq/ess-helm/matrix-tools/internal/cmd/render-config"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/syn2mas"
	"github.com/element-hq/ess-helm/matrix-tools/internal/cmd/tcpwait"
	"github.com/element-hq/ess-helm/matrix-tools/internal/pkg/secret"
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
				RenderConfig: &renderconfig.RenderConfigOptions{
					Files: []string{"file1"},
				},
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
				RenderConfig: &renderconfig.RenderConfigOptions{
					Files:  []string{"file1", "file2"},
					Output: "outputFile",
				},
			},
			err: false,
		},
		{
			name: "Correct usage of render-config",
			args: []string{"cmd", "render-config", "-output", "outputFile", "file1", "file2"},
			expected: &Options{
				RenderConfig: &renderconfig.RenderConfigOptions{
					Files:  []string{"file1", "file2"},
					Output: "outputFile",
				},
				Command: RenderConfig,
			},
			err: false,
		},
		{
			name: "Correct usage of render-config with append arrays",
			args: []string{"cmd", "render-config", "-output", "outputFile", "-array-overwrite-keys", "permissions,another_array", "file1", "file2"},
			expected: &Options{
				RenderConfig: &renderconfig.RenderConfigOptions{
					Files:              []string{"file1", "file2"},
					Output:             "outputFile",
					ArrayOverwriteKeys: []string{"permissions", "another_array"},
				},
				Command: RenderConfig,
			},
			err: false,
		},
		{
			name: "Correct usage of tcp-wait",
			args: []string{"cmd", "tcpwait", "-address", "address:port"},
			expected: &Options{
				TcpWait: &tcpwait.TcpWaitOptions{
					Address: "address:port",
				},
				Command: TCPWait,
			},
			err: false,
		},
		{
			name: "Correct usage of generate-secrets",
			args: []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:rand32", "-labels", "mykey=myval"},
			expected: &Options{
				GenerateSecrets: &generatesecrets.GenerateSecretsOptions{
					GeneratedSecrets: []generatesecrets.GeneratedSecret{
						{ArgValue: "secret1:value1:rand32", Name: "secret1", Key: "value1", Type: secret.Rand32, GeneratorArgs: make([]string, 0)},
					},
					Labels: map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets", "mykey": "myval"},
				},
				Command: GenerateSecrets,
			},
			err: false,
		},

		{
			name: "Multiple generated secrets",
			args: []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:rand32,secret2:value2:signingkey,secret3:value3:registration:/registration-templates/registration.yaml"},
			expected: &Options{
				GenerateSecrets: &generatesecrets.GenerateSecretsOptions{
					GeneratedSecrets: []generatesecrets.GeneratedSecret{
						{ArgValue: "secret1:value1:rand32", Name: "secret1", Key: "value1", Type: secret.Rand32, GeneratorArgs: make([]string, 0)},
						{ArgValue: "secret2:value2:signingkey", Name: "secret2", Key: "value2", Type: secret.SigningKey, GeneratorArgs: make([]string, 0)},
						{ArgValue: "secret3:value3:registration:/registration-templates/registration.yaml", Name: "secret3", Key: "value3", Type: secret.Registration, GeneratorArgs: []string{"/registration-templates/registration.yaml"}},
					},
					Labels: map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets"},
				},
				Command: GenerateSecrets,
			},
			err: false,
		},
		{
			name: "Multiple generator args in secrets",
			args: []string{"cmd", "generate-secrets", "-secrets", "secret1:value1:rsa:4096:der"},
			expected: &Options{
				GenerateSecrets: &generatesecrets.GenerateSecretsOptions{
					GeneratedSecrets: []generatesecrets.GeneratedSecret{
						{ArgValue: "secret1:value1:rsa:4096:der", Name: "secret1", Key: "value1", Type: secret.RSA, GeneratorArgs: []string{"4096", "der"}},
					},
					Labels: map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-init-secrets"},
				},
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
			args: []string{"cmd", "deployment-markers", "-step", "pre", "-markers", "cm1:key1:value1:value1,cm1:key2:value2:value1;value2"},
			expected: &Options{
				DeploymentMarkers: &deploymentmarkers.DeploymentMarkersOptions{
					DeploymentMarkers: []deploymentmarkers.DeploymentMarker{
						{Name: "cm1", Key: "key1", Step: "pre", NewValue: "value1", AllowedValues: []string{"value1"}},
						{Name: "cm1", Key: "key2", Step: "pre", NewValue: "value2", AllowedValues: []string{"value1", "value2"}},
					},
					Labels: map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers"},
				},
				Command: DeploymentMarkers,
			},
			err: false,
		},
		{
			name: "Multiple deployment-markers (post step)",
			args: []string{"cmd", "deployment-markers", "-step", "post", "-markers", "cm1:key1:value1:value1,cm1:key2:value2:value1;value2"},
			expected: &Options{
				DeploymentMarkers: &deploymentmarkers.DeploymentMarkersOptions{
					DeploymentMarkers: []deploymentmarkers.DeploymentMarker{
						{Name: "cm1", Key: "key1", Step: "post", NewValue: "value1", AllowedValues: []string{"value1"}},
						{Name: "cm1", Key: "key2", Step: "post", NewValue: "value2", AllowedValues: []string{"value1", "value2"}},
					},
					Labels: map[string]string{"app.kubernetes.io/managed-by": "matrix-tools-deployment-markers"},
				},
				Command: DeploymentMarkers,
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

		{
			name: "Proper syntax of syn2mas",
			args: []string{"cmd", "syn2mas", "-config", "file1", "-synapse-config", "file2"},
			expected: &Options{
				Syn2Mas: &syn2mas.Syn2MasOptions{
					MASConfig:     "file1",
					SynapseConfig: "file2",
				},
				Command: Syn2Mas,
			},
			err: false,
		},
		{
			name: "Wrong syntax of syn2mas",
			args: []string{"cmd", "syn2mas"},
			expected: &Options{
				Command: Syn2Mas,
			},
			err: true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			options, err := ParseArgs(tc.args)
			if tc.err {
				assert.Error(t, err)
				assert.Nil(t, options)
			} else {
				assert.Nil(t, err)
				assert.Equal(t, tc.expected, options)
			}
		})
	}
}
