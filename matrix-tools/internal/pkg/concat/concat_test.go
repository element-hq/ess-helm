// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

package concat

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

const TESTDATA_DIR = "testdata"

var FILECONTENTS_T = []byte(`1234567`)
var FILECONTENTS_1 = []byte(`ABCDEFG`)
var FILECONTENTS_2 = []byte(`HIJKLMN`)

func TestConcat(t *testing.T) {
	testCases := []struct {
		name           string
		targetContents []byte
		filesContents  [][]byte
	}{
		{
			name:           "No Files",
			targetContents: FILECONTENTS_T,
			filesContents:  [][]byte{},
		},
		{
			name:           "Single File",
			targetContents: FILECONTENTS_T,
			filesContents: [][]byte{
				FILECONTENTS_1,
			},
		},
		{
			name:           "Multiple Files",
			targetContents: FILECONTENTS_T,
			filesContents: [][]byte{
				FILECONTENTS_1,
				FILECONTENTS_2,
			},
		},
		{
			name:           "Multiple Files in Reverse Order",
			targetContents: FILECONTENTS_T,
			filesContents: [][]byte{
				FILECONTENTS_2,
				FILECONTENTS_1,
			},
		},
		{
			name:           "Single File with Empty Target",
			targetContents: []byte{},
			filesContents: [][]byte{
				FILECONTENTS_1,
			},
		},
		{
			name:           "Multiple Files with Empty Target",
			targetContents: []byte{},
			filesContents: [][]byte{
				FILECONTENTS_1,
				FILECONTENTS_2,
			},
		},
		{
			name:           "Single File with New Target File",
			targetContents: nil,
			filesContents: [][]byte{
				FILECONTENTS_1,
			},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			targetPath := filepath.Join(t.TempDir(), "targetFile")
			expected := make([]byte, 0)
			if tc.targetContents != nil {
				err := os.WriteFile(targetPath, tc.targetContents, 0644)
				if err != nil {
					t.Fatalf("Failed to initialize target file: %v", err)
				}
				expected = append(expected, tc.targetContents...)
			}
			readers := make([]io.Reader, len(tc.filesContents))
			for i, fileContents := range tc.filesContents {
				readers[i] = bytes.NewBuffer(fileContents)
				expected = append(expected, fileContents...)
			}
			err := Concat(readers, targetPath)
			if err != nil {
				t.Fatalf("Failed with error: %v", err)
			}
			readAndCompare(t, targetPath, expected)
		})
	}

	t.Run("Unwriteable Target File", func(t *testing.T) {
		var contents = []byte(`1234567`)
		targetPath := filepath.Join(t.TempDir(), "targetFile")
		err := os.WriteFile(targetPath, contents, 0444)
		if err != nil {
			t.Fatalf("Failed to initialize target file: %v", err)
		}
		err = Concat([]io.Reader{bytes.NewBuffer([]byte(`abc`))}, targetPath)
		if err == nil {
			t.Fatalf("Got no error for writing to unwriteable target file")
		}
		readAndCompare(t, targetPath, contents)
	})
}

func readAndCompare(t *testing.T, targetPath string, expected []byte) {
	result, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatalf("Failed to read target file: %v", err)
	}
	if !reflect.DeepEqual(result, expected) {
		t.Fatalf("expected: %v, got: %v", expected, result)
	}
}
