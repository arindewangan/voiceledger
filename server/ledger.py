"""SQLite storage layer for VoiceLedger.

Two tables:
  entries  - every money movement (expense or income)
  budgets  - monthly per-category spending budgets

Timestamps are stored as local ISO-8601 strings so date-bucketing
(today / this week / this month) matches what the user experiences.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


@dataclass
class Entry:
    id: int
    kind: str          # "expense" | "income"
    amount: float
    currency: str
    note: str          # merchant/description for expenses
    category: str      # category for expenses
    source: str        # source for income
    created_at: str    # ISO-8601 local


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Ledger:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        if os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # -- schema ----------------------------------------------------------
    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kind       TEXT NOT NULL CHECK (kind IN ('expense','income')),
                amount     REAL NOT NULL CHECK (amount > 0),
                currency   TEXT NOT NULL DEFAULT 'INR',
                note       TEXT NOT NULL DEFAULT '',
                category   TEXT NOT NULL DEFAULT 'other',
                source     TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
            CREATE INDEX IF NOT EXISTS idx_entries_kind    ON entries(kind);
            CREATE TABLE IF NOT EXISTS budgets (
                category   TEXT PRIMARY KEY,
                amount     REAL NOT NULL CHECK (amount > 0)
            );
            """
        )
        self._conn.commit()

    # -- writes ----------------------------------------------------------
    def add_expense(self, amount: float, note: str, category: str,
                    currency: str = "INR", created_at: str | None = None) -> Entry:
        if amount <= 0:
            raise ValueError("amount must be positive")
        ts = created_at or _now_iso()
        cur = self._conn.execute(
            "INSERT INTO entries (kind, amount, currency, note, category, created_at)"
            " VALUES ('expense', ?, ?, ?, ?, ?)",
            (amount, currency, note.strip(), category, ts),
        )
        self._conn.commit()
        return self.get_entry(cur.lastrowid)

    def add_income(self, amount: float, source: str,
                   currency: str = "INR", created_at: str | None = None) -> Entry:
        if amount <= 0:
            raise ValueError("amount must be positive")
        ts = created_at or _now_iso()
        cur = self._conn.execute(
            "INSERT INTO entries (kind, amount, currency, note, source, created_at)"
            " VALUES ('income', ?, ?, '', ?, ?)",
            (amount, currency, source.strip(), ts),
        )
        self._conn.commit()
        return self.get_entry(cur.lastrowid)

    def undo_last(self) -> Entry | None:
        """Delete the most recently added entry and return it (or None)."""
        row = self._conn.execute(
            "SELECT * FROM entries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        self._conn.execute("DELETE FROM entries WHERE id = ?", (row["id"],))
        self._conn.commit()
        return Entry(
            id=row["id"], kind=row["kind"], amount=row["amount"],
            currency=row["currency"], note=row["note"], category=row["category"],
            source=row["source"], created_at=row["created_at"],
        )

    def set_budget(self, category: str, amount: float) -> None:
        if amount <= 0:
            raise ValueError("budget must be positive")
        self._conn.execute(
            "INSERT INTO budgets (category, amount) VALUES (?, ?)"
            " ON CONFLICT(category) DO UPDATE SET amount = excluded.amount",
            (category.strip().lower(), amount),
        )
        self._conn.commit()

    # -- reads -----------------------------------------------------------
    def get_entry(self, entry_id: int) -> Entry:
        row = self._conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> Entry:
        return Entry(
            id=row["id"], kind=row["kind"], amount=row["amount"],
            currency=row["currency"], note=row["note"], category=row["category"],
            source=row["source"], created_at=row["created_at"],
        )

    def _entries_since(self, since: date, kind: str = "expense") -> list[Entry]:
        rows = self._conn.execute(
            "SELECT * FROM entries WHERE kind = ? AND substr(created_at, 1, 10) >= ?"
            " ORDER BY created_at",
            (kind, since.isoformat()),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def summary(self, period: str = "month") -> dict[str, Any]:
        """Totals for today / this week / this month with category breakdown."""
        today = date.today()
        if period == "today":
            since = today
        elif period == "week":
            since = today - timedelta(days=today.weekday())  # Monday
        else:
            period = "month"
            since = today.replace(day=1)
        expenses = self._entries_since(since, "expense")
        income = self._entries_since(since, "income")
        by_category: dict[str, float] = {}
        for e in expenses:
            by_category[e.category] = by_category.get(e.category, 0.0) + e.amount
        return {
            "period": period,
            "since": since.isoformat(),
            "total_expense": round(sum(e.amount for e in expenses), 2),
            "total_income": round(sum(e.amount for e in income), 2),
            "count": len(expenses),
            "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])},
        }

    def budget_status(self) -> list[dict[str, Any]]:
        """Spent-vs-budget per category for the current month."""
        spent = self.summary("month")["by_category"]
        rows = self._conn.execute("SELECT category, amount FROM budgets").fetchall()
        out = []
        for r in rows:
            cat, budget = r["category"], r["amount"]
            used = spent.get(cat, 0.0)
            out.append({
                "category": cat,
                "budget": budget,
                "spent": round(used, 2),
                "remaining": round(budget - used, 2),
                "over": used > budget,
                "pct": round(100.0 * used / budget, 1) if budget else 0.0,
            })
        return sorted(out, key=lambda d: -d["pct"])

    def search(self, keyword: str, days: int = 30) -> list[Entry]:
        """Case-insensitive keyword search over notes, categories and sources."""
        since = (date.today() - timedelta(days=days)).isoformat()
        kw = f"%{keyword.lower()}%"
        rows = self._conn.execute(
            "SELECT * FROM entries WHERE substr(created_at, 1, 10) >= ?"
            " AND (lower(note) LIKE ? OR lower(category) LIKE ? OR lower(source) LIKE ?)"
            " ORDER BY created_at DESC",
            (since, kw, kw, kw),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
