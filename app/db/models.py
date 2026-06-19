"""SQLAlchemy ORM models matching the task schema.

  accounts(user_id, balance, currency)
  transactions(id, user_id, amount, merchant, date)
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), default="UZS")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.user_id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    merchant: Mapped[str] = mapped_column(String(120))
    date: Mapped[dt.date] = mapped_column()
