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

	"go.yaml.in/yaml/v2"
)

type RegistrationFile struct {
	HSToken string `yaml:"hs_token"`
	ASToken string `yaml:"as_token"`
}

func generateOrUpdateRegistration(templatePath string, existingRegistration []byte) ([]byte, error) {
	if existingRegistration != nil {
		return updateRegistration(templatePath, existingRegistration)
	}
	return generateNewRegistration(templatePath)
}

func generateNewRegistration(templatePath string) ([]byte, error) {
	hsToken, err := generateRandomString(32)
	if err != nil {
		return nil, errors.New("failed to generate hs token: " + err.Error())
	}
	asToken, err := generateRandomString(32)
	if err != nil {
		return nil, errors.New("failed to generate as token: " + err.Error())
	}
	return generateRegistration(templatePath, hsToken, asToken)
}

func updateRegistration(templatePath string, existingRegistration []byte) ([]byte, error) {
	var registration RegistrationFile
	err := yaml.Unmarshal(existingRegistration, &registration)
	if err != nil {
		return nil, errors.New("failed to read existing registration file: " + err.Error())
	}
	return generateRegistration(templatePath, []byte(registration.HSToken), []byte(registration.ASToken))
}

func generateRegistration(templatePath string, hsToken []byte, asToken []byte) ([]byte, error) {
	fileReader, err := os.Open(templatePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}

	fileContent, err := io.ReadAll(fileReader)
	if err != nil {
		return nil, errors.New("failed to read from reader: " + err.Error())
	}

	fileContent = bytes.ReplaceAll(fileContent, []byte("${AS_TOKEN}"), asToken)
	fileContent = bytes.ReplaceAll(fileContent, []byte("${HS_TOKEN}"), hsToken)

	return fileContent, nil
}
