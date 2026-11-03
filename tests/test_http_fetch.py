import asyncio
import socket

import httpx
import pytest

from oracles_service.upstream import HttpAttestUpstream, _default_http_fetch, sha256_digest


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0):
        self.chunks = chunks
        self.delay = delay
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.fixture
async def network(monkeypatch):
    state = {"addresses": ["8.8.8.8"], "dns": [], "requests": [], "stream": Stream([b"ok"]), "headers": {}, "status": 200}

    async def resolve(host, port, **kwargs):
        state["dns"].append((host, port))
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in state["addresses"]]

    async def handle(request):
        state["requests"].append(request)
        return httpx.Response(state["status"], headers=state["headers"], stream=state["stream"])

    client = httpx.AsyncClient

    def make_client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return client(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    monkeypatch.setattr(httpx, "AsyncClient", make_client)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "100.64.0.1", "::1", "fe80::1", "::ffff:127.0.0.1", "224.0.0.1"])
async def test_private_resolution_never_connects(network, address):
    network["addresses"] = ["8.8.8.8", address]
    result = await HttpAttestUpstream(_default_http_fetch(1)).observe(kind="public_relay", subject="https://relay.example/health")
    assert result.status == "unreachable" and result.digest is None
    assert not network["requests"]


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["127.1", "2130706433", "0x7f000001"])
async def test_numeric_alias_resolution_is_checked(network, host):
    network["addresses"] = ["127.0.0.1"]
    result = await HttpAttestUpstream(_default_http_fetch(1)).observe(kind="public_relay", subject=f"https://{host}/health")
    assert result.status == "unreachable"
    assert not network["requests"]


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
async def test_connection_pinned_with_original_tls_authority(network, address):
    network["addresses"] = [address]
    result = await _default_http_fetch(1)("https://relay.example:8443/health?q=1")
    assert result.body == b"ok"
    assert network["dns"] == [("relay.example", 8443)]
    request = network["requests"][0]
    assert request.url.host == address and request.url.port == 8443
    assert request.url.raw_path == b"/health?q=1"
    assert request.headers["host"] == "relay.example:8443"
    assert request.extensions["sni_hostname"] == "relay.example"
    assert network["stream"].closed


@pytest.mark.asyncio
@pytest.mark.parametrize("size,observed", [(1024 * 1024, True), (1024 * 1024 + 1, False)])
async def test_stream_byte_limit(network, size, observed):
    payload = b"x" * size
    network["stream"] = Stream([payload[:500000], payload[500000:]])
    result = await HttpAttestUpstream(_default_http_fetch(1)).observe(kind="public_relay", subject="https://relay.example/")
    assert result.status == ("observed" if observed else "unreachable")
    assert result.digest == (sha256_digest(payload) if observed else None)
    assert network["stream"].closed


@pytest.mark.asyncio
async def test_compressed_response_rejected_before_decoding(network):
    network["headers"] = {"Content-Encoding": "gzip"}
    network["stream"] = Stream([b"not even valid gzip"])
    result = await HttpAttestUpstream(_default_http_fetch(1)).observe(kind="public_relay", subject="https://relay.example/")
    assert result.status == "unreachable" and result.digest is None
    assert network["stream"].closed


@pytest.mark.asyncio
async def test_total_deadline_stops_progressing_stream(network):
    network["stream"] = Stream([b"x"] * 100, delay=.01)
    result = await HttpAttestUpstream(_default_http_fetch(.03)).observe(kind="public_relay", subject="https://relay.example/")
    assert result.status == "unreachable" and result.digest is None
    assert network["stream"].closed


@pytest.mark.asyncio
async def test_deadline_includes_dns(network, monkeypatch):
    async def slow(*args, **kwargs):
        await asyncio.sleep(10)
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", slow)
    result = await HttpAttestUpstream(_default_http_fetch(.01)).observe(kind="public_relay", subject="https://relay.example/")
    assert result.status == "unreachable"
    assert not network["requests"]


@pytest.mark.asyncio
async def test_redirect_not_followed(network):
    network["status"] = 302
    network["headers"] = {"Location": "https://127.0.0.1/"}
    result = await HttpAttestUpstream(_default_http_fetch(1)).observe(kind="public_relay", subject="https://relay.example/")
    assert result.status == "unreachable"
    assert len(network["requests"]) == 1
    assert network["stream"].closed
