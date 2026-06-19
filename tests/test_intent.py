"""V1 intent-classification logic (mock brain)."""
import pytest

from app.schemas import Intent
from app.services import LanguageModel

llm = LanguageModel()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected",
    [
        ("What is the price of Bitcoin today?", Intent.QUERY),
        ("Send a message to my manager saying I will be late.", Intent.ACTION),
        ("Hi there, nice to meet you!", Intent.SMALLTALK),
        ("Set an alarm for 7am", Intent.ACTION),
        ("How are you?", Intent.SMALLTALK),
        ("What time is it?", Intent.QUERY),
    ],
)
async def test_intent_classification(text, expected):
    assert await llm.classify_intent(text) == expected


@pytest.mark.asyncio
async def test_empty_defaults_to_smalltalk():
    assert await llm.classify_intent("") == Intent.SMALLTALK
