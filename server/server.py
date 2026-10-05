"""VoiceLedger MCP server — an Alexa+ track entry.

Self-hosted MCP server (Streamable HTTP on /mcp, MCP spec 2025-11-25+)
backing a voice-first personal finance ledger. Every tool returns short,
speakable sentences suitable for an Alexa+ voice response.
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.mcpserver import MCPServer
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from .auth import BearerAuthMiddleware
from .brain import Brain
from .config import load_config
from .ledger import Ledger

log = logging.getLogger("voiceledger.server")

config = load_config()
ledger = Ledger(config.db_path)
brain = Brain(model_id=config.bedrock_model_id, region=config.bedrock_region)

server = MCPServer("voiceledger")


def _inr(amount: float) -> str:
    """Format an amount for speech, e.g. 1250 -> '1,250 rupees'."""
    return f"{int(round(amount)):,} rupees"


# ---------------------------------------------------------------- tools
@server.tool(description="Record an expense: amount and a note. Category is auto-detected.")
async def log_expense(amount: float, note: str) -> str:
    """Log a spend. amount: positive number. note: what it was for, e.g. 'groceries'."""
    if amount <= 0:
        return "The amount needs to be more than zero. What did you spend?"
    category, _source = brain.categorize(note, amount)
    entry = ledger.add_expense(amount, note, category, currency=config.currency)
    today_total = ledger.summary("today")["total_expense"]
    return (
        f"Logged {_inr(amount)} for {entry.note} under {entry.category}. "
        f"You've spent {_inr(today_total)} today."
    )


@server.tool(description="Record income with its source.")
async def log_income(amount: float, source: str) -> str:
    """Log income. amount: positive number. source: e.g. 'salary', 'freelance'."""
    if amount <= 0:
        return "The amount needs to be more than zero. How much did you earn?"
    entry = ledger.add_income(amount, source, currency=config.currency)
    month_income = ledger.summary("month")["total_income"]
    return (
        f"Recorded {_inr(amount)} income from {entry.source}. "
        f"Total income this month is {_inr(month_income)}."
    )


@server.tool(description="Undo the most recently logged entry ('undo that').")
async def undo_last() -> str:
    """Reverse the last entry, whether it was an expense or income."""
    entry = ledger.undo_last()
    if entry is None:
        return "There's nothing to undo. Your ledger is empty."
    if entry.kind == "expense":
        return f"Undone. Removed the {_inr(entry.amount)} expense for {entry.note}."
    return f"Undone. Removed the {_inr(entry.amount)} income from {entry.source}."


@server.tool(description="Spending totals for today, this week, or this month, by category.")
async def spend_summary(period: str = "month") -> str:
    """Summarize spending. period: 'today', 'week', or 'month' (default)."""
    period = (period or "month").strip().lower()
    if period not in ("today", "week", "month"):
        period = "month"
    s = ledger.summary(period)
    total = s["total_expense"]
    label = {"today": "today", "week": "this week", "month": "this month"}[period]
    if total <= 0:
        return f"You haven't logged any spending {label}."
    parts = [f"{cat} {_inr(amt)}" for cat, amt in s["by_category"].items()]
    breakdown = ", ".join(parts[:4])
    extra = f", and {len(parts) - 4} more categories" if len(parts) > 4 else ""
    return (
        f"You spent {_inr(total)} {label} across {s['count']} expenses. "
        f"Top categories: {breakdown}{extra}."
    )


@server.tool(description="Check spending against monthly category budgets, with over-budget alerts.")
async def budget_status() -> str:
    """Report spent-vs-budget per category for the current month."""
    statuses = ledger.budget_status()
    if not statuses:
        return "You haven't set any budgets yet. Say 'set a budget' to add one."
    over = [b for b in statuses if b["over"]]
    lines = []
    for b in statuses:
        lines.append(
            f"{b['category']}: {_inr(b['spent'])} of {_inr(b['budget'])}"
            + (" - over budget!" if b["over"] else "")
        )
    summary = "; ".join(lines)
    if over:
        names = ", ".join(b["category"] for b in over)
        return f"Budget check. {summary}. Alert: you are over budget on {names}."
    return f"Budget check. {summary}. You're within all budgets. Nice going."


@server.tool(description="Set a monthly budget for a spending category.")
async def set_budget(category: str, amount: float) -> str:
    """Set a monthly budget. category: e.g. 'dining'. amount: positive number."""
    if amount <= 0:
        return "The budget needs to be more than zero. What should the budget be?"
    ledger.set_budget(category, amount)
    return f"Set your monthly {category.strip().lower()} budget to {_inr(amount)}."


@server.tool(description="AI-generated insight on your spending: trends, anomalies, one tip.")
async def spending_insights() -> str:
    """Generate a short spoken insight about this month's spending."""
    summary = ledger.summary("month")
    budgets = ledger.budget_status()
    text, _source = brain.insights(summary, budgets)
    return text


@server.tool(description="Find past entries by keyword, e.g. cabs last week.")
async def search_expenses(keyword: str, days: int = 30) -> str:
    """Search expenses and income by keyword. days: how far back to look (default 30)."""
    keyword = (keyword or "").strip()
    if not keyword:
        return "What should I search for?"
    days = max(1, min(int(days), 365))
    results = ledger.search(keyword, days=days)
    if not results:
        return f"I couldn't find anything matching '{keyword}' in the last {days} days."
    expenses = [e for e in results if e.kind == "expense"]
    total = sum(e.amount for e in expenses)
    shown = "; ".join(f"{_inr(e.amount)} for {e.note}" for e in results[:3])
    more = f", and {len(results) - 3} more" if len(results) > 3 else ""
    return (
        f"Found {len(results)} matching entries totalling {_inr(total)}. "
        f"{shown}{more}."
    )


@server.tool(description="Health check: confirms the VoiceLedger server is running.")
async def ping() -> str:
    """Simple liveness check."""
    return "VoiceLedger is running and your ledger is ready."


# ------------------------------------------------------- HTTP app
def create_app(stateless: bool = False) -> "Starlette":  # noqa: F821
    """Build the Starlette app: MCP Streamable HTTP + auth + CORS + health.

    stateless=True disables session tracking (useful for tests and simple
    deployments); the wire protocol is identical.
    """
    app = server.streamable_http_app(
        json_response=False, stateless_http=stateless
    )

    async def healthz(_request):
        return JSONResponse({"status": "ok", "service": "voiceledger"})

    app.router.routes.append(Route("/healthz", healthz, methods=["GET"]))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BearerAuthMiddleware, token=config.api_token)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    db_dir = os.path.dirname(os.path.abspath(config.db_path))
    print(f"VoiceLedger MCP server starting on {config.host}:{config.port}")
    print(f"  MCP endpoint : http://{config.host}:{config.port}/mcp")
    print(f"  Health       : http://{config.host}:{config.port}/healthz")
    print(f"  Database     : {os.path.abspath(config.db_path)}")
    print(f"  Bedrock      : {'enabled (' + config.bedrock_model_id + ')' if config.bedrock_model_id else 'offline fallback mode'}")
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
