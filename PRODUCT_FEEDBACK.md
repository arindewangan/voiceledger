# Product Feedback

Honest notes on the tools and platforms we used while building
VoiceLedger for the Amazon App Dev Hackathon 2026.

## MCP Python SDK — 8/10

The official `mcp` SDK made exposing our 9 tools over Streamable HTTP
straightforward: decorating async functions as tools just works, and the
protocol plumbing (session IDs, SSE streams, JSON-RPC framing) stayed out
of the way. Knocked points off because a v2 rename (`FastMCP` ->
`MCPServer`) broke most tutorials and examples online, so setup involved
more trial and error than it should have. A first-party in-process test
story for Streamable HTTP would be the other big win — we had to spawn a
real uvicorn subprocess from pytest for the smoke test.

## Amazon Bedrock (converse API) — 8/10

The `converse` API itself is genuinely pleasant: one unified request
shape across model families, no per-provider client quirks, and it made
both expense categorization and spending-insight generation trivial to
prompt. What hurt was model-ID discovery — finding which inference
profiles are available in which region, and getting the exact ID string
right, took far longer than writing the actual integration code. Clearer
region/model lookup tooling would earn this a 9.

## SQLite — 9/10

Zero-ops, zero-config, and more than fast enough for a personal-finance
ledger: single-file storage, WAL-friendly, trivially inspectable during
demos. The only reason it is not a 10 is the usual caveat — we would need
to graduate to a server database if this ever became multi-user.

## Starlette / uvicorn — 9/10

A boring-in-the-best-way foundation. Starlette's routing and middleware
(Bearer <redacted> CORS for the demo console) took minutes to wire up, and
uvicorn served SSE streams for the MCP transport without a hiccup.
Production-ready feel with hobby-project ergonomics.

## Devpost — 7/10

The submission flow works, but it is fiddly for multi-part hackathon
projects: coordinating the written submission, demo video upload, and
friction-log / feedback bonuses across separate forms feels scattered,
and previewing how the final project page reads is harder than it should
be. Still, the hackathon hub features (tracks, mini challenges, team
coordination) do their job.

## Overall

MCP + Bedrock is a genuinely great hackathon stack: the MCP spec gave us
a clean, voice-friendly tool boundary and the official SDK removed most
protocol toil, while Bedrock's converse API turned two of our hardest
features (auto-categorization and natural-language insights) into simple
prompt calls — with a deterministic offline fallback for when the cloud
is not cooperating. We would pick this stack again without hesitation.
