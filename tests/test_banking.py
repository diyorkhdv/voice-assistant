"""V2 banking logic: intent routing, repository correctness, no-data handling."""
import pytest

from app.schemas import BankingIntent
from app.services import LanguageModel

llm = LanguageModel()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected",
    [
        ("How much money do I have?", BankingIntent.BALANCE),
        ("What's my balance?", BankingIntent.BALANCE),
        ("Where did I spend money yesterday?", BankingIntent.TRANSACTIONS),
        ("Show my recent transactions", BankingIntent.TRANSACTIONS),
        ("Tell me a joke", BankingIntent.UNKNOWN),
    ],
)
async def test_banking_intent(text, expected):
    assert await llm.classify_banking_intent(text) == expected


@pytest.mark.asyncio
async def test_synthesis_uses_only_db_numbers():
    data = {"kind": "balance", "found": True, "balance": "1250", "currency": "UZS"}
    answer = await llm.synthesize_answer("How much do I have?", data)
    assert "1250" in answer and "UZS" in answer


@pytest.mark.asyncio
async def test_no_transactions_message():
    data = {"kind": "transactions", "currency": "UZS", "transactions": []}
    answer = await llm.synthesize_answer("Where did I spend?", data)
    assert "no" in answer.lower() or "don't" in answer.lower()
