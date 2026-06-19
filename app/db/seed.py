"""Seed deterministic demo data so the V2 endpoint works out of the box.

Idempotent: running twice will not duplicate rows.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.db.database import SessionLocal, init_db
from app.db.models import Account, Transaction

TODAY = dt.date(2026, 6, 19)
YDAY = TODAY - dt.timedelta(days=1)


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        if db.execute(select(Account).limit(1)).first():
            return  # already seeded

        accounts = [
            Account(user_id=1, balance=Decimal("1250.00"), currency="UZS"),
            Account(user_id=2, balance=Decimal("500.00"), currency="USD"),
            Account(user_id=3, balance=Decimal("0.00"), currency="UZS"),  # no spending
        ]
        txns = [
            Transaction(user_id=1, amount=Decimal("50000.00"), merchant="Korzinka", date=YDAY),
            Transaction(user_id=1, amount=Decimal("12000.00"), merchant="Yandex Go", date=TODAY),
            Transaction(user_id=1, amount=Decimal("8500.00"), merchant="Evos", date=TODAY - dt.timedelta(days=3)),
            Transaction(user_id=2, amount=Decimal("42.50"), merchant="Starbucks", date=YDAY),
            Transaction(user_id=2, amount=Decimal("120.00"), merchant="Uber", date=TODAY - dt.timedelta(days=2)),
            # user_id=3 intentionally has NO transactions (no-data edge case)
        ]
        db.add_all(accounts + txns)
        db.commit()


if __name__ == "__main__":
    seed()
    print("Database seeded.")
