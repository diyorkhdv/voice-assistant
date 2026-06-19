"""Language model (the "Brain").

Three responsibilities:
  1. classify_intent          -> V1: Query / Action / SmallTalk
  2. classify_banking_intent  -> V2: balance / transactions / unknown
  3. synthesize_answer        -> V2: natural-language answer grounded ONLY in DB data

Design notes
------------
* We use the Chat Completions API with JSON mode for classification so the
  output is a strict, parseable contract (no brittle string matching).
* SQL safety: the LLM NEVER writes SQL. It only chooses an intent label from a
  closed set. The actual data fetch is a parameterized ORM query (see
  app/db/repository.py). This removes the LLM-driven SQL-injection surface
  entirely while keeping the UX of "ask in natural language".
* Anti-hallucination: synthesize_answer receives the data as structured JSON
  and is instructed to use only those numbers; in mock mode we template the
  answer deterministically from the same data, so numbers can never drift.
"""
from __future__ import annotations

import json

from app.config import get_settings
from app.schemas import BankingIntent, Intent
from app.services.openai_client import get_async_client

INTENT_SYSTEM_PROMPT = """You classify a single user utterance into exactly one intent.

Definitions:
- "Query": the user asks for information or an answer (e.g. "What time is it?", "What is the price of Bitcoin today?").
- "Action": the user requests that a task be performed (e.g. "Set an alarm", "Send a message to my manager").
- "SmallTalk": greetings or general conversation with no information request or task (e.g. "How are you?", "Nice to meet you").

Rules:
- Choose the single best label even if the speech is short, noisy, or ambiguous.
- If the utterance is empty or unintelligible, default to "SmallTalk".
- Respond with JSON only: {"intent": "Query" | "Action" | "SmallTalk"}."""

BANKING_SYSTEM_PROMPT = """You route a personal-banking voice request to one data intent.

Intents:
- "balance": the user wants their current account balance / how much money they have.
- "transactions": the user asks about spending, purchases, or transaction history (where/when/how much they spent, recent payments).
- "unknown": the request is unrelated to balance or transactions, or is unintelligible.

Respond with JSON only: {"intent": "balance" | "transactions" | "unknown"}."""

SYNTH_SYSTEM_PROMPT = """You are a personal banking voice assistant.
You will receive structured account data as JSON. Write ONE short, natural,
spoken-style sentence answering the user's question.

Hard constraints:
- Use ONLY the numbers, currencies, merchants and dates present in the JSON.
- Never invent or estimate values. If the data shows nothing, say so plainly.
- Keep it concise and friendly, suitable for text-to-speech. No markdown."""


class LanguageModel:
    def __init__(self) -> None:
        self.settings = get_settings()

    # ------------------------------- V1 -------------------------------- #
    async def classify_intent(self, transcript: str) -> Intent:
        if self.settings.use_mock:
            return self._mock_intent(transcript)

        client = get_async_client()
        resp = await client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": transcript or ""},
            ],
        )
        raw = json.loads(resp.choices[0].message.content)
        try:
            return Intent(raw["intent"])
        except (KeyError, ValueError):
            return Intent.SMALLTALK

    # ------------------------------- V2 -------------------------------- #
    async def classify_banking_intent(self, transcript: str) -> BankingIntent:
        if self.settings.use_mock:
            return self._mock_banking_intent(transcript)

        client = get_async_client()
        resp = await client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": BANKING_SYSTEM_PROMPT},
                {"role": "user", "content": transcript or ""},
            ],
        )
        raw = json.loads(resp.choices[0].message.content)
        try:
            return BankingIntent(raw["intent"])
        except (KeyError, ValueError):
            return BankingIntent.UNKNOWN

    async def synthesize_answer(self, transcript: str, data: dict) -> str:
        if self.settings.use_mock:
            return self._mock_synthesize(data)

        client = get_async_client()
        payload = {"question": transcript, "data": data}
        resp = await client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYNTH_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
        )
        return resp.choices[0].message.content.strip()

    # ----------------------------- Mocks ------------------------------- #
    @staticmethod
    def _mock_intent(transcript: str) -> Intent:
        t = (transcript or "").lower()
        action_kw = ("set ", "send ", "create", "remind", "play", "turn on", "turn off",
                     "book", "schedule", "call ", "open ", "buy ", "transfer")
        smalltalk_kw = ("hi", "hello", "hey", "how are you", "nice to meet",
                        "good morning", "good evening", "what's up", "thanks")
        if any(k in t for k in action_kw):
            return Intent.ACTION
        if any(t.startswith(k) or k in t for k in smalltalk_kw):
            return Intent.SMALLTALK
        if t.strip().endswith("?") or t.startswith(("what", "when", "where", "who",
                                                     "why", "how", "is ", "are ", "can ",
                                                     "do ", "does ")):
            return Intent.QUERY
        return Intent.SMALLTALK

    @staticmethod
    def _mock_banking_intent(transcript: str) -> BankingIntent:
        t = (transcript or "").lower()
        if any(k in t for k in ("balance", "how much money", "how much do i have",
                                "account", "funds", "left")):
            return BankingIntent.BALANCE
        if any(k in t for k in ("spend", "spent", "transaction", "purchase", "buy",
                                "bought", "payment", "paid", "where did")):
            return BankingIntent.TRANSACTIONS
        return BankingIntent.UNKNOWN

    @staticmethod
    def _mock_synthesize(data: dict) -> str:
        kind = data.get("kind")
        if kind == "balance":
            if data.get("found"):
                return f"Your current balance is {data['balance']} {data['currency']}."
            return "I couldn't find an account on file for you."
        if kind == "transactions":
            txns = data.get("transactions", [])
            if not txns:
                return "You don't have any recent transactions on record."
            t = txns[0]
            return (f"Your most recent transaction was {t['amount']} {t['currency']} "
                    f"at {t['merchant']} on {t['date']}.")
        return ("I can help with your balance or your recent transactions. "
                "Which would you like?")
