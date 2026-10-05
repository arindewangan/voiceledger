"""End-to-end protocol smoke test: real Streamable HTTP against a live server.

A real uvicorn server is spawned on a free port (stateful sessions, exactly
like production). Mirrors the curl sequence: initialize ->
notifications/initialized -> tools/list -> tools/call, plus the 401 auth
negative case.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys

import httpx
import pytest

TOKEN=<redacted>
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rpc_headers(session_id: str | None = None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


def _parse_sse(text: str) -> dict:
    """Extract the first JSON-RPC data event from an SSE stream."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    raise AssertionError(f"no SSE data event in response: {text[:200]!r}")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """Spawn the real VoiceLedger server; tear it down after the module."""
    tmp = tmp_path_factory.mktemp("proto")
    port = _free_port()
    env = dict(os.environ,
API_TOKEN=<redacted>
               LEDGER_DB=str(tmp / "proto.db"),
               BEDROCK_MODEL_ID="",
               PORT=str(port),
               PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.server"],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        import urllib.request
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            proc.poll()
            assert proc.returncode is None, "server process died during startup"
            __import__("time").sleep(0.15)
        else:
            raise RuntimeError("server did not become healthy in time")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
async def mcp_client(live_server):
    # trust_env=False: this sandbox's no_proxy contains bracketed IPv6
    # entries that httpx 0.28.1 fails to parse (environment quirk, not
    # a product bug). Traffic is local anyway.
    async with httpx.AsyncClient(base_url=live_server, timeout=30,
                                 trust_env=False) as client:
        yield client


async def test_full_protocol_flow(mcp_client: httpx.AsyncClient):
    # 1. initialize
    resp = await mcp_client.post(
        "/mcp",
        headers=_rpc_headers(),
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-11-25",
                         "capabilities": {},
                         "clientInfo": {"name": "pytest", "version": "1"}}},
    )
    assert resp.status_code == 200
    session_id = resp.headers.get("mcp-session-id")
    assert session_id, "server must issue a session id"
    init = _parse_sse(resp.text)
    assert init["result"]["protocolVersion"] == "2025-11-25"
    assert init["result"]["serverInfo"]["name"] == "voiceledger"

    headers = _rpc_headers(session_id)

    # 2. notifications/initialized
    resp = await mcp_client.post(
        "/mcp", headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert resp.status_code in (200, 202)

    # 3. tools/list
    resp = await mcp_client.post(
        "/mcp", headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    listed = _parse_sse(resp.text)
    names = {t["name"] for t in listed["result"]["tools"]}
    assert {"log_expense", "log_income", "undo_last", "spend_summary",
            "budget_status", "set_budget", "spending_insights",
            "search_expenses", "ping"} <= names

    # 4. tools/call log_expense
    resp = await mcp_client.post(
        "/mcp", headers=headers,
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "log_expense",
                         "arguments": {"amount": 450, "note": "groceries"}}},
    )
    called = _parse_sse(resp.text)
    assert called["result"]["isError"] is False
    text = called["result"]["content"][0]["text"]
    assert "450 rupees" in text
    assert "groceries" in text

    # 5. tools/call undo_last reverses it
    resp = await mcp_client.post(
        "/mcp", headers=headers,
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "undo_last", "arguments": {}}},
    )
    undone = _parse_sse(resp.text)
    assert "Undone" in undone["result"]["content"][0]["text"]


async def test_auth_rejected_without_token(mcp_client: httpx.AsyncClient):
    resp = await mcp_client.post(
        "/mcp",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-11-25",
                         "capabilities": {},
                         "clientInfo": {"name": "pytest", "version": "1"}}},
    )
    assert resp.status_code == 401


async def test_healthz_open(mcp_client: httpx.AsyncClient):
    resp = await mcp_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
