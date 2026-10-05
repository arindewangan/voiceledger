# VoiceLedger

**"Talk money. It listens."** — a voice-first personal finance ledger for the
Alexa+ track of the Amazon App Dev Hackathon 2026.

VoiceLedger is a self-hosted **MCP server** (Streamable HTTP, MCP spec
2025-11-25+) that turns spoken money updates into a real ledger: log expenses
by voice, get auto-categorization, budget alerts, and AI spending insights
powered by **Amazon Bedrock** — with a fully working offline fallback so the
demo never breaks.

## Quick start

```bash
cd voiceledger
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure (all secrets via environment, never committed)
export API_TOKEN=<redacted>
export LEDGER_DB="data/ledger.db"        # default
export BEDROCK_MODEL_ID=""               # empty = offline fallback mode
export BEDROCK_REGION="ap-south-1"

# Optional: seed a month of realistic INR demo data
python scripts/seed_demo.py

# Start the server
python -m server.server
# MCP endpoint: http://127.0.0.1:8000/mcp
# Health:       http://127.0.0.1:8000/healthz
```

Open `demo/index.html` in a browser for the simulated Alexa+ voice console.
Set the token field to your `API_TOKEN` and press **Reconnect**.

## MCP tools

| Tool | What it does |
|---|---|
| `log_expense` | Record spend — amount + note; category auto-detected |
| `log_income` | Record income with its source |
| `undo_last` | "Undo that" — reverses the last entry |
| `spend_summary` | Totals for today / week / month, by category |
| `budget_status` | Spent-vs-budget per category, over-budget alerts |
| `set_budget` | Set a monthly category budget |
| `spending_insights` | Bedrock-generated insight: trends, anomalies, one tip |
| `search_expenses` | Find entries by keyword |
| `ping` | Health check |

All tool outputs are short, speakable sentences — no markdown, no tables.

## Run the tests

```bash
pytest -q
```

28 tests: ledger logic, budget alerts, undo, offline categorizer, tool
outputs, and a full protocol smoke test against a live server subprocess.

## Bedrock integration

Set `BEDROCK_MODEL_ID` (e.g. `anthropic.claude-3-5-sonnet-20240620-v1:0`) and
provide AWS credentials in the standard way (`~/.aws/credentials`,
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, or an IAM role). The server uses
the `converse` API for expense categorization and monthly spending insights.
If the model is unset or any AWS call fails, `brain.py` transparently falls
back to the deterministic rule-based categorizer and template insights —
the demo works with **zero AWS setup**.

## Project layout

```
server/        MCP server (mcp SDK), SQLite ledger, Bedrock brain, Bearer <redacted>
demo/          simulated Alexa+ voice console (static HTML, talks to /mcp)
tests/         pytest suite (28 tests)
scripts/       seed_demo.py — one month of realistic INR transactions
```

## License

MIT — see [LICENSE](LICENSE).
