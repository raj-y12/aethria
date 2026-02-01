# AETHRIA Backend – Quick Start & Configuration

**Version:** 1.0  
**Status:** Production-Ready

---

## Overview

AETHRIA backend is an autonomous agent-based DealFlow OS. Pipeline: **Scout → Reviewer → Partner → Portfolio**.

---

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Configuration

Create `.env` file in **project root** (not backend):

```bash
OPENAI_API_KEY=your_key_here
```

### Run agents only

```bash
cd backend
python run_system.py
```

### Run full stack (backend + frontend + agents)

From **project root**:

```bash
python run.py
```

This starts:
- FastAPI backend on http://localhost:8000
- Frontend (Vite) on http://localhost:3000
- DealFlow agents (Scout, Reviewer, Partner, Portfolio)

### API for frontend

The app-front-end fetches startups from `GET /api/startups`. Run the API server:

```bash
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

With the frontend dev server on port 3000, ensure both are running when using live backend data.

---

## Configuration

Environment variables (all optional except `OPENAI_API_KEY`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | **(required)** | Your OpenAI API key |
| `STORAGE_PATH` | `data/startups.json` | Discovery storage file |
| `SETTINGS_PATH` | `data/settings.json` | Settings file (agent toggles, cost budget) |
| `SCOUT_INTERVAL_SECONDS` | 300 | Scout cycle interval |
| `REVIEWER_INTERVAL_SECONDS` | 60 | Reviewer cycle interval |
| `PARTNER_INTERVAL_SECONDS` | 30 | Partner cycle interval |
| `SCOUT_MODEL` | `gpt-5-nano` | OpenAI model for scouts |
| `REVIEWER_MODEL` | `gpt-5-nano` | OpenAI model for reviewer |
| `PARTNER_USE_LLM` | `true` | Enable LLM fallback for partner edge cases |
| `PORTFOLIO_DIR` | `data/portfolio` | Portfolio data directory |

---

## Cost Discipline

- **Scout**: One LLM call per scout per cycle
- **Reviewer**: One LLM call per review
- **Partner**: Zero LLM calls (rule-based; optional fallback for edge cases)
- **Portfolio**: No LLM calls

**Default Model:** `gpt-5-nano` (cost-efficient)

---

## Data Storage

**Discovery pipeline:** `data/startups.json` (or `STORAGE_PATH`) – Scout/Reviewer/Partner data.

**Settings:** `data/settings.json` – Agent toggles (scouts_enabled, reviewers_enabled, partners_enabled), cost budget, portfolio behavior.

**Portfolio memory:** `data/portfolio/` – startups, decisions, portfolio, rejections, watchlist, signals, agent_metrics.

---

## Testing

Tests are in `backend/tests/`:

- `test_scouts.py` – Scout layer
- `test_end_to_end.py` – Scout → Reviewer flow
- `test_partner_flow.py` – Scout → Reviewer → Partner flow
- `test_portfolio_layer.py` – Portfolio components

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) – System architecture and layers
- [VERDICT_MEMO_AND_REVIEWER_SCORING.md](VERDICT_MEMO_AND_REVIEWER_SCORING.md) – Verdict, memo, and reviewer scoring
- [AUDIT_DEALFLOW.md](AUDIT_DEALFLOW.md) – Storage/adapters/memo audit
- [CODEBASE_EVALUATION.md](CODEBASE_EVALUATION.md) – Codebase evaluation and recommendations

---

## Known Limitations

1. Single JSON file storage (migration to Postgres planned at scale)
2. No meta-layer (agent evolution not implemented)
3. Single partner (no multi-partner voting)

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.
