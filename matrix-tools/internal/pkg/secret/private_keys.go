// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package secret

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"fmt"
)

func marshallKeyIntoDER(key any) ([]byte, error) {
	keyBytes, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, err
	}

	return keyBytes, nil
}

func marshallKeyIntoPEM(rsaPrivateKey *rsa.PrivateKey) ([]byte, error) {
	return pem.EncodeToMemory(
		&pem.Block{
			Type:  "RSA PRIVATE KEY",
			Bytes: x509.MarshalPKCS1PrivateKey(rsaPrivateKey),
		}), nil
}

func generateRSA(bits int, format string) ([]byte, error) {
	rsaPrivateKey, err := rsa.GenerateKey(rand.Reader, bits)
	if err != nil {
		return nil, err
	}
	switch format {
	case "pem":
		return marshallKeyIntoPEM(rsaPrivateKey)
	case "der":
		return marshallKeyIntoDER(rsaPrivateKey)
	default:
		return nil, fmt.Errorf("%s key format unsupported", format)
	}
}

func generateEcdsaPrime256v1DER() ([]byte, error) {
	ecdsaPrivateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, err
	}
	return marshallKeyIntoDER(ecdsaPrivateKey)
}
