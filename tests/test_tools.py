"""Tests for the MCP tool functions (voice-first outputs)."""

import pytest

import server.server as srv
from server.ledger import Ledger


@pytest.fixture()
def tools_ledger(tmp_path, monkeypatch):
    """Swap the server module's ledger for an isolated temp DB."""
    ledger = Ledger(str(tmp_path / "tools.db"))
    monkeypatch.setattr(srv, "ledger", ledger)
    yield ledger
    ledger.close()


async def test_log_expense_speakable(tools_ledger):
    out = await srv.log_expense(450, "groceries at BigBasket")
    assert "450 rupees" in out
    assert "groceries" in out
    assert "{" not in out  # no JSON in voice output


async def test_log_expense_rejects_bad_amount(tools_ledger):
    out = await srv.log_expense(-5, "bad")
    assert "more than zero" in out


async def test_log_income(tools_ledger):
    out = await srv.log_income(50000, "salary")
    assert "50,000 rupees" in out
    assert "salary" in out


async def test_undo_tool(tools_ledger):
    await srv.log_expense(100, "chai")
    out = await srv.undo_last()
    assert "Undone" in out
    assert "chai" in out
    out = await srv.undo_last()
    assert "nothing to undo" in out


async def test_spend_summary_tool(tools_ledger):
    await srv.log_expense(450, "groceries")
    await srv.log_expense(150, "chai")
    out = await srv.spend_summary("today")
    assert "600 rupees" in out
    assert "groceries" in out
    out = await srv.spend_summary("nonsense-period")
    assert "this month" in out  # falls back to month


async def test_budget_flow(tools_ledger):
    out = await srv.budget_status()
    assert "haven't set any budgets" in out
    out = await srv.set_budget("dining", 1000)
    assert "1,000 rupees" in out
    await srv.log_expense(600, "Swiggy dinner")
    out = await srv.budget_status()
    assert "within all budgets" in out
    await srv.log_expense(600, "Zomato lunch")
    out = await srv.budget_status()
    assert "over budget" in out
    assert "dining" in out


async def test_spending_insights_tool(tools_ledger):
    await srv.log_expense(450, "groceries")
    out = await srv.spending_insights()
    assert "450" in out
    assert len(out.split(". ")) <= 4  # short, speakable


async def test_search_expenses_tool(tools_ledger):
    await srv.log_expense(120, "Uber cab")
    out = await srv.search_expenses("cab")
    assert "120 rupees" in out
    out = await srv.search_expenses("spaceship")
    assert "couldn't find" in out
    out = await srv.search_expenses("")
    assert "What should I search for" in out


async def test_ping_tool():
    out = await srv.ping()
    assert "VoiceLedger is running" in out
