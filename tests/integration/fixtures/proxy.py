# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Proxy server fixture for browser tests.

This module provides a simple HTTP forward proxy that routes *.localhost
domains to 127.0.0.1. This is necessary because browsers performing HTTPS
requests need proper DNS resolution, and *.localhost may not always resolve
correctly in all environments.

The proxy handles HTTP CONNECT tunneling by establishing a raw TCP tunnel
to the upstream server. For *.localhost domains, it rewrites the destination
to 127.0.0.1 while preserving the original hostname for SNI.
"""

import asyncio
import contextlib
import ssl
import tempfile
from pathlib import Path

import pytest

from ..artifacts import CertKey


class LocalhostTunnelProxy:
    """
    Simple HTTP CONNECT proxy that routes *.localhost to 127.0.0.1.

    For HTTPS requests, browsers use HTTP CONNECT to establish a tunnel.
    This proxy intercepts the CONNECT request, extracts the target hostname,
    and if it ends with .localhost, connects to 127.0.0.1 instead while
    allowing the browser to perform its own TLS handshake with the server.

    The browser must be configured to ignore HTTPS errors since the
    certificates presented by the server won't match what the browser
    expects for the hostname.
    """

    def __init__(self):
        self._server: asyncio.Server | None = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle an incoming client connection."""
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8", errors="ignore").strip()
            parts = request_str.split(" ")

            if len(parts) < 2:
                writer.close()
                return

            method = parts[0]

            if method != "CONNECT":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                await writer.drain()
                writer.close()
                return

            target = parts[1]
            if ":" in target:
                host, port_str = target.rsplit(":", 1)
                port = int(port_str)
            else:
                host = target
                port = 443

            while True:
                header_line = await reader.readline()
                if header_line in (b"\r\n", b"\n", b""):
                    break

            actual_host = "127.0.0.1" if host.endswith(".localhost") else host

            try:
                upstream_reader, upstream_writer = await asyncio.open_connection(actual_host, port)
            except Exception:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                writer.close()
                return

            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()

            async def pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
                try:
                    while True:
                        data = await src.read(65536)
                        if not data:
                            break
                        dst.write(data)
                        await dst.drain()
                except (ConnectionResetError, BrokenPipeError, ssl.SSLError, OSError):
                    pass
                finally:
                    with contextlib.suppress(Exception):
                        dst.close()

            await asyncio.gather(
                pipe(reader, upstream_writer),
                pipe(upstream_reader, writer),
                return_exceptions=True,
            )

        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> tuple[str, int]:
        """Start the proxy server and return the (host, port) tuple."""
        self._server = await asyncio.start_server(self.handle_client, host, port)
        addrs = self._server.sockets[0].getsockname() if self._server.sockets else (host, port)
        return addrs[0], addrs[1]

    async def stop(self):
        """Stop the proxy server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()


@pytest.fixture(scope="session")
async def proxy_server(root_ca: CertKey):
    """
    Start a proxy server that routes *.localhost to 127.0.0.1.

    This proxy is used by Playwright to route browser requests to the
    local k3d cluster. The browser is configured with ignore_https_errors=True
    to accept the test CA certificates.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        ca_cert_path = tmpdir_path / "ca.pem"
        with open(ca_cert_path, "w") as f:
            f.write(root_ca.cert_as_pem())

        proxy = LocalhostTunnelProxy()
        host, port = await proxy.start()

        proxy_url = f"http://{host}:{port}"

        yield proxy_url

        await proxy.stop()
