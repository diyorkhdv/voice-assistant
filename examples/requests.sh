#!/usr/bin/env bash
# Example requests. In mock mode the transcript is taken from the filename after
# `__transcript__`; with a real OPENAI_API_KEY, pass an actual .wav/.mp3 file.
set -e
BASE="${BASE:-http://localhost:8000}"

echo "== health =="
curl -s "$BASE/health"; echo

echo "== V1: Query =="
curl -s -X POST "$BASE/api/v1/voice-intent" \
  -F 'file=@/dev/null;filename=clip__transcript__What_is_the_price_of_Bitcoin_today.wav;type=audio/wav' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print({k:d[k] for k in ("transcript","intent","reply_text","latency_ms")})'

echo "== V1: Action =="
curl -s -X POST "$BASE/api/v1/voice-intent" \
  -F 'file=@/dev/null;filename=clip__transcript__Set_an_alarm_for_7am.wav;type=audio/wav' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["intent"])'

echo "== V2: Balance (user 1) =="
curl -s -X POST "$BASE/api/v2/banking-assistant" \
  -F 'user_id=1' \
  -F 'file=@/dev/null;filename=clip__transcript__How_much_money_do_I_have.wav;type=audio/wav' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["answer_text"]);print(d["data"])'

echo "== V2: Transactions yesterday (user 1) =="
curl -s -X POST "$BASE/api/v2/banking-assistant" \
  -F 'user_id=1' \
  -F 'file=@/dev/null;filename=clip__transcript__Where_did_I_spend_money_yesterday.wav;type=audio/wav' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["answer_text"])'

echo "== V2: No data (user 3) =="
curl -s -X POST "$BASE/api/v2/banking-assistant" \
  -F 'user_id=3' \
  -F 'file=@/dev/null;filename=clip__transcript__Where_did_I_spend_money.wav;type=audio/wav' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["answer_text"])'
