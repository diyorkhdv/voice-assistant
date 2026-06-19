"""Data access — the ONLY place that touches the DB.

Every query is a parameterized SQLAlchemy ORM statement. The LLM never supplies
SQL or column/table names; it only chooses an intent label. ``user_id`` is bound
as a parameter, so even a malicious transcript cannot inject SQL.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, Transaction


class BankingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_balance(self, user_id: int) -> dict:
        # Parameterized: user_id is bound, never string-formatted into SQL.
        account = self.db.execute(
            select(Account).where(Account.user_id == user_id)
        ).scalar_one_or_none()

        if account is None:
            return {"kind": "balance", "found": False, "user_id": user_id}

        return {
            "kind": "balance",
            "found": True,
            "user_id": user_id,
            "balance": f"{account.balance:.2f}".rstrip("0").rstrip("."),
            "currency": account.currency,
        }

    def get_transactions(self, user_id: int, limit: int = 5,
                         since: dt.date | None = None,
                         until: dt.date | None = None) -> dict:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        if since is not None:
            stmt = stmt.where(Transaction.date >= since)
        if until is not None:
            stmt = stmt.where(Transaction.date <= until)
        stmt = stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit)

        rows = self.db.execute(stmt).scalars().all()
        account = self.db.execute(
            select(Account).where(Account.user_id == user_id)
        ).scalar_one_or_none()
        currency = account.currency if account else "UZS"

        return {
            "kind": "transactions",
            "user_id": user_id,
            "currency": currency,
            "transactions": [
                {
                    "amount": f"{t.amount:.2f}".rstrip("0").rstrip("."),
                    "merchant": t.merchant,
                    "date": t.date.isoformat(),
                    "currency": currency,
                }
                for t in rows
            ],
        }
