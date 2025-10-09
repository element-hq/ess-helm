// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
)

func marshallKey(key any) ([]byte, error) {
	keyBytes, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, err
	}

	return keyBytes, nil
}

func generateRSA() ([]byte, error) {
	rsaPrivateKey, err := rsa.GenerateKey(rand.Reader, 4096)
	if err != nil {
		return nil, err
	}
	return marshallKey(rsaPrivateKey)
}

func generateEcdsaPrime256v1() ([]byte, error) {
	ecdsaPrivateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, err
	}
	return marshallKey(ecdsaPrivateKey)
}
