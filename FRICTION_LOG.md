# Friction Log

Things that slowed us down while building VoiceLedger. Submitted for
the hackathon's friction-log bonus.

## 1. MCP Python SDK v2 renamed `FastMCP` to `MCPServer`

Most tutorials, blog posts, and Stack Overflow answers for the Python MCP
SDK still show `from mcp.server.fastmcp import FastMCP`, which no longer
exists in SDK v2. The code samples run, the imports fail, and the error
does not suggest the new name. A migration note at the top of the v2
docs (or a deprecated alias) would have saved us a solid hour of
confused searching.

## 2. Streamable HTTP has no in-process test story

The SDK makes it easy to *serve* an MCP endpoint, but there is no
supported way to exercise Streamable HTTP transports inside pytest. We
ended up spawning a real uvicorn subprocess from the test suite and
talking to it over loopback — it works, but it is slow and flaky in CI.
A lightweight in-process transport client for tests would be a huge
quality-of-life win for SDK users.

## 3. Bedrock model-ID discovery is painful

The `converse` API is a joy to use; *finding* a valid model ID for your
region is not. Inference profile ARNs, per-region availability, and
legacy vs. on-demand naming are scattered across docs pages, and the
error when you get the ID wrong is generic. A single
region-filtered "list models I can call" CLI command would fix this.

## 4. Voice-first output discipline is a design constraint the SDK does not help with

Every tool result in VoiceLedger must be a short, speakable sentence —
no markdown, no tables, no hedging. That constraint lives entirely in
our prompt copy and review discipline; the SDK offers no lint, schema
hint, or output-shaping hook for "speakable" responses. Even a docs page
of voice-first tool-writing patterns would help future builders.

## 5. Sandbox proxy env vars vs. httpx bracketed IPv6 `no_proxy`

Our sandbox sets proxy environment variables, and httpx's parsing of
bracketed IPv6 entries (`[::1]`) in `no_proxy` did not match what we
expected, so loopback MCP traffic kept getting routed through the proxy
during testing. It took real debugging time to pin the failure on proxy
config rather than our server code. Subtle, environment-specific, and
the kind of thing better error surfacing would catch.
