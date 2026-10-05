"""Tests for the SQLite ledger layer."""

import pytest

from server.ledger import Ledger


def test_add_and_get_expense(ledger: Ledger):
    e = ledger.add_expense(450, "groceries at BigBasket", "groceries")
    assert e.amount == 450
    assert e.category == "groceries"
    assert ledger.get_entry(e.id).note == "groceries at BigBasket"


def test_negative_amount_rejected(ledger: Ledger):
    with pytest.raises(ValueError):
        ledger.add_expense(-10, "bad", "other")
    with pytest.raises(ValueError):
        ledger.add_income(0, "nothing")


def test_undo_last_expense(ledger: Ledger):
    ledger.add_expense(100, "chai", "dining")
    e2 = ledger.add_expense(200, "cab", "transport")
    undone = ledger.undo_last()
    assert undone.id == e2.id
    assert undone.note == "cab"
    assert ledger.summary("month")["count"] == 1


def test_undo_last_income(ledger: Ledger):
    ledger.add_income(5000, "salary")
    undone = ledger.undo_last()
    assert undone.kind == "income"
    assert undone.source == "salary"
    assert ledger.summary("month")["total_income"] == 0


def test_undo_empty_ledger(ledger: Ledger):
    assert ledger.undo_last() is None


def test_summary_by_category(ledger: Ledger):
    ledger.add_expense(450, "groceries", "groceries")
    ledger.add_expense(150, "chai", "dining")
    ledger.add_expense(300, "more groceries", "groceries")
    s = ledger.summary("month")
    assert s["total_expense"] == 900
    assert s["by_category"]["groceries"] == 750
    assert s["by_category"]["dining"] == 150
    assert s["count"] == 3


def test_summary_periods(ledger: Ledger):
    # old entry should not appear in today's summary
    ledger.add_expense(100, "old", "other", created_at="2020-01-01T10:00:00+05:30")
    ledger.add_expense(250, "today", "dining")
    assert ledger.summary("today")["total_expense"] == 250
    assert ledger.summary("month")["total_expense"] == 250


def test_budget_alerts(ledger: Ledger):
    ledger.set_budget("dining", 500)
    ledger.add_expense(300, "lunch", "dining")
    status = ledger.budget_status()
    assert len(status) == 1
    assert status[0]["spent"] == 300
    assert status[0]["remaining"] == 200
    assert status[0]["over"] is False
    # push over budget
    ledger.add_expense(300, "dinner", "dining")
    status = ledger.budget_status()
    assert status[0]["over"] is True
    assert status[0]["remaining"] == -100


def test_budget_update(ledger: Ledger):
    ledger.set_budget("dining", 500)
    ledger.set_budget("dining", 1000)  # overwrite
    status = ledger.budget_status()
    assert status[0]["budget"] == 1000


def test_search(ledger: Ledger):
    ledger.add_expense(120, "Uber cab to office", "transport")
    ledger.add_expense(80, "Ola cab home", "transport")
    ledger.add_expense(450, "groceries", "groceries")
    hits = ledger.search("cab")
    assert len(hits) == 2
    hits = ledger.search("GROCERIES")
    assert len(hits) == 1
    assert ledger.search("spaceship") == []
