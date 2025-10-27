# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import datetime
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytz
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import Certificate
from cryptography.x509.oid import NameOID
from platformdirs import user_cache_dir


@dataclass(frozen=True)
class CertKey:
    ca: CertKey | None
    cert: Certificate
    key: RSAPrivateKey

    def get_root_ca(self) -> CertKey:
        if self.ca is None:
            return self
        return self.ca.get_root_ca()

    def cert_bundle_as_pem(self):
        bundle = []
        bundle.append(self.cert.public_bytes(encoding=serialization.Encoding.PEM).decode("utf-8"))
        ca = self.ca
        while ca is not None:
            # We only append this CA cert if it isn't the root
            if ca.ca is not None:
                bundle.append(self.ca.cert_as_pem())
            ca = ca.ca
        return "".join(bundle)

    def cert_as_pem(self):
        return self.cert.public_bytes(encoding=serialization.Encoding.PEM).decode("utf-8")

    def key_as_pem(self):
        return self.key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

    @classmethod
    def from_dict(cls, kv):
        return CertKey(
            ca=CertKey.from_dict(kv["ca"]) if kv["ca"] else None,
            cert=x509.load_pem_x509_certificate(kv["cert"].encode("utf-8"), default_backend()),
            key=load_pem_private_key(kv["key"].encode("utf-8"), None, default_backend()),
        )

    def to_json_mapping(self) -> dict[str, Any]:
        return {
            "ca": self.ca.to_json_mapping() if self.ca else None,
            "cert": self.cert_as_pem(),
            "key": self.key_as_pem(),
        }


def get_ca(name, issuing_ca=None) -> CertKey:
    ca_filename = Path(user_cache_dir("pytest-ess", "element")) / Path(name.lower().replace(" ", "-"))
    cert_path = ca_filename.with_suffix(".crt")
    key_path = ca_filename.with_suffix(".key")
    if not ca_filename.parent.exists():
        os.makedirs(ca_filename.parent, exist_ok=True)
    certkey = None

    if cert_path.exists() and key_path.exists():
        with open(key_path, "rb") as pem_in:
            private_key = load_pem_private_key(pem_in.read(), None, default_backend())
            if not isinstance(private_key, rsa.RSAPrivateKey):
                raise ValueError("Expected RSA private key")
        with open(cert_path, "rb") as pem_in:
            cert = x509.load_pem_x509_certificate(pem_in.read(), default_backend())
        if cert.not_valid_after_utc > pytz.UTC.localize(datetime.datetime.now()):
            certkey = CertKey(ca=issuing_ca, cert=cert, key=private_key)

    if not certkey:
        certkey = generate_ca(name, issuing_ca)
        with open(key_path, "wb") as pem_out:
            pem_out.write(certkey.key_as_pem().encode("utf-8"))
        with open(cert_path, "wb") as pem_out:
            pem_out.write(certkey.cert_as_pem().encode("utf-8"))

    # Remove unused bundle - given we should only need to trust the root CA, that the tests will construct the
    # bundle appropriate for ingresses, and that a bundle of CA certs wasn't super useful this file was unneeded
    bundle_path = (ca_filename.parent / (ca_filename.name + "-bundle")).with_suffix(".pem")
    if bundle_path.exists():
        bundle_path.unlink()

    return certkey


def generate_ca(name, issuing_ca=None) -> CertKey:
    two_days = datetime.timedelta(2, 0, 0)
    three_months = datetime.timedelta(90, 0, 0)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    public_key = private_key.public_key()
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(
        x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ess"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "localhost"),
            ]
        )
    )
    if issuing_ca:
        builder = builder.issuer_name(issuing_ca.cert.subject)
    else:
        builder = builder.issuer_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, name),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ess"),
                    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "localhost"),
                ]
            )
        )
    builder = builder.not_valid_before(datetime.datetime.today() - two_days)
    builder = builder.not_valid_after(datetime.datetime.today() + three_months)
    builder = builder.serial_number(int(uuid.uuid4()))
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    )
    builder = builder.add_extension(
        x509.KeyUsage(True, False, False, False, False, True, True, False, False),
        critical=True,
    )
    builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
    if issuing_ca:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuing_ca.cert.public_key()), critical=False
        )
        certificate = builder.sign(issuing_ca.key, hashes.SHA256(), default_backend())
        ca = CertKey(ca=issuing_ca, cert=certificate, key=private_key)
    else:
        builder = builder.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(public_key), critical=False)
        certificate = builder.sign(private_key, hashes.SHA256(), default_backend())
        ca = CertKey(ca=None, cert=certificate, key=private_key)
    return ca


def generate_cert(ca, dns_names: list[str]) -> CertKey:
    one_day = datetime.timedelta(1, 0, 0)

    # Now we want to generate a cert from that root
    cert_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    new_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, dns_names[0]),
        ]
    )
    x509_certificate = (
        x509.CertificateBuilder()
        .subject_name(new_subject)
        .issuer_name(ca.cert.subject)
        .public_key(cert_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.today() - one_day)
        .not_valid_after(datetime.datetime.today() + one_day)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(dns_name) for dns_name in dns_names]),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(cert_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.cert.public_key()), critical=False)
    )
    cert = x509_certificate.sign(ca.key, hashes.SHA256(), default_backend())

    return CertKey(ca=ca, cert=cert, key=cert_key)
