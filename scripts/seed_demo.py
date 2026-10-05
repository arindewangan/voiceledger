#!/usr/bin/env python3
"""Seed one month of realistic INR demo transactions for VoiceLedger.

Usage:
    LEDGER_DB=data/ledger.db API_TOKEN=... python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.brain import offline_categorize  # noqa: E402
from server.ledger import Ledger  # noqa: E402

random.seed(42)

TRANSACTIONS: list[tuple[str, int, int]] = [
    # (note, amount, times_per_month)
    ("groceries at BigBasket", 1200, 4),
    ("vegetables from kirana store", 350, 6),
    ("milk and bread", 120, 8),
    ("Swiggy dinner order", 650, 5),
    ("Zomato lunch", 420, 4),
    ("cafe coffee with friends", 380, 3),
    ("Uber cab to office", 280, 10),
    ("Ola cab home", 260, 8),
    ("metro recharge", 500, 2),
    ("petrol", 1500, 2),
    ("electricity bill", 1450, 1),
    ("wifi broadband bill", 999, 1),
    ("mobile recharge", 349, 1),
    ("Netflix subscription", 649, 1),
    ("movie at PVR", 900, 2),
    ("Myntra shoes", 2200, 1),
    ("Amazon electronics", 3500, 1),
    ("pharmacy medicines", 640, 2),
    ("gym membership", 2000, 1),
    ("Udemy course", 499, 1),
    ("book purchase", 750, 1),
    ("OYO hotel weekend trip", 2800, 1),
    ("flight booking", 5200, 1),
    ("dinner at dhaba", 850, 2),
    ("chai and snacks", 90, 10),
    ("Blinkit instant groceries", 480, 5),
    ("Zepto late-night snacks", 320, 3),
    ("parking", 100, 6),
    ("salon haircut", 600, 1),
]


def jitter(amount: int) -> float:
    return round(amount * random.uniform(0.85, 1.2), 2)


def main() -> None:
    db_path = os.environ.get("LEDGER_DB", "data/ledger.db")
    ledger = Ledger(db_path)
    now = datetime.now().astimezone()

    count = 0
    for note, amount, times in TRANSACTIONS:
        for _ in range(times):
            days_ago = random.randint(0, 29)
            ts = (now - timedelta(days=days_ago,
                                  hours=random.randint(0, 23),
                                  minutes=random.randint(0, 59)))
            category = offline_categorize(note)
            ledger.add_expense(jitter(amount), note, category,
                               created_at=ts.isoformat(timespec="seconds"))
            count += 1

    # monthly income
    salary_day = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
    ledger.add_income(85000, "salary", created_at=salary_day.isoformat(timespec="seconds"))
    ledger.add_income(6000, "freelance", created_at=(now - timedelta(days=12)).isoformat(timespec="seconds"))

    # budgets (dining deliberately tight so the demo triggers an alert)
    for category, budget in [("dining", 4000), ("groceries", 9000),
                             ("transport", 6000), ("entertainment", 3000),
                             ("shopping", 8000)]:
        ledger.set_budget(category, budget)

    total = ledger.summary("month")["total_expense"]
    print(f"Seeded {count} expenses + 2 income entries into {db_path}")
    print(f"Month-to-date spend: Rs. {total:,.0f}")
    ledger.close()


if __name__ == "__main__":
    main()
