"""End-to-end API tests through FastAPI TestClient (mock mode)."""
from tests.conftest import make_audio


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["mock_mode"] is True


# ------------------------------- V1 -------------------------------- #
def test_v1_query(client):
    r = client.post("/api/v1/voice-intent", files=make_audio("What is the price of Bitcoin today"))
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "Query"
    assert body["reply_text"] == "I have categorized your request as Query."
    assert body["audio_base64"]  # non-empty
    assert body["latency_ms"] >= 0


def test_v1_action(client):
    r = client.post("/api/v1/voice-intent", files=make_audio("Send a message to my manager"))
    assert r.json()["intent"] == "Action"


def test_v1_rejects_bad_type(client):
    r = client.post("/api/v1/voice-intent", files={"file": ("note.txt", b"hello", "text/plain")})
    assert r.status_code == 415


# ------------------------------- V2 -------------------------------- #
def test_v2_balance(client):
    r = client.post(
        "/api/v2/banking-assistant",
        data={"user_id": 1},
        files=make_audio("How much money do I have"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "balance"
    assert "1250" in body["answer_text"]      # pulled from DB
    assert body["data"]["balance"] == "1250"


def test_v2_transactions_yesterday(client):
    r = client.post(
        "/api/v2/banking-assistant",
        data={"user_id": 1},
        files=make_audio("Where did I spend money yesterday"),
    )
    body = r.json()
    assert body["intent"] == "transactions"
    assert "Korzinka" in body["answer_text"]
    assert "50000" in body["answer_text"]


def test_v2_no_data(client):
    # user_id=3 has an account but no transactions.
    r = client.post(
        "/api/v2/banking-assistant",
        data={"user_id": 3},
        files=make_audio("Where did I spend money"),
    )
    body = r.json()
    assert body["intent"] == "transactions"
    assert body["data"]["transactions"] == []
    assert "no" in body["answer_text"].lower() or "don't" in body["answer_text"].lower()


def test_v2_sql_injection_is_harmless(client):
    """A malicious transcript cannot inject SQL: user_id is integer-bound and the
    LLM never produces SQL. The request must still succeed safely."""
    r = client.post(
        "/api/v2/banking-assistant",
        data={"user_id": 1},
        files=make_audio("balance; DROP TABLE accounts;--"),
    )
    assert r.status_code == 200
    # Table is intact: a follow-up balance query still works.
    r2 = client.post(
        "/api/v2/banking-assistant",
        data={"user_id": 1},
        files=make_audio("How much money do I have"),
    )
    assert r2.json()["data"]["balance"] == "1250"


def test_v2_requires_user_id(client):
    r = client.post("/api/v2/banking-assistant", files=make_audio("balance"))
    assert r.status_code == 422
