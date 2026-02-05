# Aethria Backend – Quick Reference

For product context, API, roadmap, and ops (including wipe script), see **[AETHRIA_PRD_AND_ARTIFACTS.md](AETHRIA_PRD_AND_ARTIFACTS.md)**. For full layer architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Run

| What | Command |
|------|---------|
| **Full stack** (backend + frontend + agents) | From repo root: `python run.py` |
| **Agents only** | `cd backend && python run_system.py` |
| **API only** (for frontend dev) | `cd backend && uvicorn api:app --reload --host 0.0.0.0 --port 8000` |

**Prerequisites:** Python 3.8+, `pip install -r backend/requirements.txt`, `.env` at repo root with `OPENAI_API_KEY`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | **(required)** | OpenAI API key |
| `STORAGE_PATH` | `data/startups.json` | Discovery storage file |
| `SETTINGS_PATH` | `data/settings.json` | Settings file |
| `SCOUT_INTERVAL_SECONDS` | 300 | Scout cycle interval |
| `REVIEWER_INTERVAL_SECONDS` | 60 | Reviewer cycle interval |
| `PARTNER_INTERVAL_SECONDS` | 30 | Partner cycle interval |
| `SCOUT_MODEL` / `REVIEWER_MODEL` | `gpt-5-nano` | Model for scouts/reviewer |
| `PARTNER_USE_LLM` | `true` | LLM fallback for partner edge cases |
| `PORTFOLIO_DIR` | `data/portfolio` | Portfolio data directory |

---

## Data Paths

- **Discovery pipeline:** `data/startups.json` (or `STORAGE_PATH`)
- **Settings:** `data/settings.json`
- **Portfolio:** `data/portfolio/` (startups, decisions, portfolio, rejections, watchlist, signals, agent_metrics)

---

## Tests

In `backend/tests/`:

- `test_scouts.py` – Scout layer
- `test_end_to_end.py` – Scout → Reviewer flow
- `test_partner_flow.py` – Scout → Reviewer → Partner flow
- `test_portfolio_layer.py` – Portfolio components

Run from `backend`: `python -m pytest tests/` (or run each script).

---

## Other Docs

- [VERDICT_MEMO_AND_REVIEWER_SCORING.md](VERDICT_MEMO_AND_REVIEWER_SCORING.md) – Verdict, memo, reviewer scoring
- [AUDIT_DEALFLOW.md](AUDIT_DEALFLOW.md) – Storage/adapters/wipe script detail
