# AETHRIA Backend

Autonomous DealFlow OS backend: Scout → Reviewer → Partner → Portfolio.

**Quick start:** From project root, `python run.py` (starts backend, frontend, and agents). Or from here: `pip install -r requirements.txt`, set `OPENAI_API_KEY` in `.env` at repo root, then `python run_system.py` for agents only; `uvicorn api:app --reload --host 0.0.0.0 --port 8000` for API.

**Documentation:** See [../docs/README.md](../docs/README.md) — [ARCHITECTURE](../docs/ARCHITECTURE.md), [BACKEND](../docs/BACKEND.md), [VERDICT_MEMO_AND_REVIEWER_SCORING](../docs/VERDICT_MEMO_AND_REVIEWER_SCORING.md), and related docs.
