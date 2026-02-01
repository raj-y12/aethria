# AETHRIA Architecture

**Version:** 1.0  
**Last Updated:** 2026-01-25  
**Status:** Production-Ready

---

## System Overview

AETHRIA is an autonomous DealFlow OS for venture capital firms. It operates as a multi-layer agentic pipeline that discovers, evaluates, and makes investment decisions autonomously.

**Pipeline:** Scout → Reviewer → Partner → Portfolio

**Design Principles:**
1. Cost-disciplined (one LLM call per agent per cycle)
2. Strict schema validation (invalid JSON = hard failure)
3. Thread-safe operations (fcntl file locking)
4. Autonomous operation (weeks-long runs)
5. Extensible architecture (easy to add layers)

---

## Layer Architecture

### Layer 1: Scout Layer (`scout/`)

**Purpose:** Discover startup opportunities using distinct cognitive strategies.

**Components:**
- `base.py`: Abstract base class for all scouts
- `schema.py`: Strict discovery schema
- `scouts.py`: 4 scout implementations
- `engine.py`: Execution engine (parallel runs)

**Scout Types:**
1. **Market-Driven Scout**: Top-down, macro trends, large markets
2. **Builder/Technical Scout**: Bottom-up, engineering-led, technical innovation
3. **Pain-Point Scout**: Pain-focused, monetizable narrow wedges
4. **Contrarian Scout**: Overlooked opportunities, non-obvious ideas

**Output Schema:**
```json
{
  "id": "uuid",
  "scout_type": "market_driven|builder_technical|pain_point|contrarian",
  "name": "string",
  "one_line": "string",
  "sector": "string",
  "problem": "string",
  "solution": "string",
  "target_users": "string",
  "why_now": "string",
  "confidence": 0.0-1.0
}
```

**Cost Discipline:**
- One LLM call per scout per cycle
- Uses `gpt-5-nano` by default (cost-efficient)
- No retries, no chaining

**Storage:** Writes to `Storage` → `data/discoveries.json`

---

### Layer 2: Reviewer Layer (`reviewer/`)

**Purpose:** Evaluate Scout discoveries with structured scoring.

**Components:**
- `base.py`: Reviewer base class
- `schema.py`: Review output schema
- `reviewer.py`: Default reviewer implementation
- `engine.py`: Execution engine

**Output Schema:**
```json
{
  "market_score": 1-10,
  "product_score": 1-10,
  "technical_score": 1-10,
  "execution_score": 1-10,
  "overall_summary": "string",
  "key_risks": ["string"],
  "verdict": "STRONG|MEDIUM|WEAK",
  "reviewer_agent_id": "string"
}
```

**Cost Discipline:**
- One LLM call per review
- Processes unreviewed entries only
- Skips already-reviewed entries

**Storage:** Updates entries in `Storage` with review data

---

### Layer 3: Partner Layer (`partner/`)

**Purpose:** Make final investment decisions (INVEST/WATCH/PASS).

**Components:**
- `schema.py`: Decision output schema
- `decision.py`: Rule-based decision engine
- `engine.py`: Execution engine

**Decision Rules:**
1. WEAK verdict → PASS
2. Critical risks → PASS
3. Average score < 6.0 → PASS
4. STRONG verdict + avg ≥ 8.0 → INVEST
5. MEDIUM verdict + avg ≥ 7.0 → WATCH
6. Default → PASS

**Output Schema:**
```json
{
  "decision": "INVEST|WATCH|PASS",
  "confidence": 1-10,
  "rationale": "string",
  "next_action": "string",
  "human_review_required": boolean,
  "partner_agent_id": "string"
}
```

**Cost Discipline:**
- Zero LLM calls by default (rule-based)
- Optional LLM fallback for edge cases only
- Deterministic, explainable decisions

**Storage:** Updates entries in `Storage` with partner decision

---

### Layer 4: Portfolio Layer (`portfolio/`)

**Purpose:** Long-term memory, signal tracking, and feedback loops.

**Components:**
- `store.py`: Portfolio Store (authoritative memory)
- `execution.py`: Execution Agent (routes decisions)
- `signals.py`: Signal Tracker (monitors watchlist)
- `feedback.py`: Feedback Loop (agent metrics)
- `cost_control.py`: Cost Controller (budgets)
- `health.py`: Health Monitor (drift detection)
- `engine.py`: Portfolio Engine (orchestrator)

**Data Files:**
- `data/portfolio/startups.json`: All discovered startups
- `data/portfolio/decisions.json`: Partner decisions
- `data/portfolio/portfolio.json`: Accepted companies
- `data/portfolio/rejections.json`: Rejected companies
- `data/portfolio/watchlist.json`: Watchlist companies
- `data/portfolio/signals.json`: Signal updates
- `data/portfolio/agent_metrics.json`: Performance metrics

**Features:**
- Append-only, versioned updates
- Signal tracking for watchlist companies
- Agent performance metrics
- Cost control and health monitoring

---

## Storage Architecture

### Discovery Storage (`storage.py`)

**Purpose:** Central storage for Scout/Reviewer/Partner pipeline.

**File:** `data/discoveries.json`

**Schema:**
```json
{
  "id": "uuid",
  "scout": { ... ScoutOutput ... },
  "review": { ... ReviewerOutput ... } | null,
  "partner": { ... PartnerOutput ... } | null,
  "timestamps": {
    "discovered_at": "ISO-8601",
    "reviewed_at": "ISO-8601" | null,
    "partnered_at": "ISO-8601" | null
  }
}
```

**Features:**
- Thread-safe file operations (fcntl locking)
- Atomic writes (temp file + rename)
- Validates JSON structure
- Extensible (partner field added cleanly)

**Migration Path:** Designed to migrate to Postgres later (schemas are clean)

---

## Execution Model

### Main Entry Point (`run_system.py`)

Runs all 4 layers in parallel:
- Scout Engine: Discovers opportunities
- Reviewer Engine: Evaluates discoveries
- Partner Engine: Makes decisions
- Portfolio Engine: Manages memory and metrics

**Configuration:**
- Environment variables for all settings
- Configurable intervals per layer
- Shared storage instance

---

## Cost Discipline

**Per-Layer Budgets:**
- Scout: One LLM call per scout per cycle
- Reviewer: One LLM call per review
- Partner: Zero LLM calls (rule-based)
- Portfolio: No LLM calls

**Global Constraints:**
- Uses `gpt-5-nano` by default (cost-efficient)
- No retries, no chaining, no hidden loops
- Designed to scale to thousands of runs

---

## Testing

**Test Files:**
- `test_scouts.py`: Scout layer tests
- `test_end_to_end.py`: Scout → Reviewer flow
- `test_partner_flow.py`: Scout → Reviewer → Partner flow
- `test_portfolio_layer.py`: Portfolio components

**Note:** Tests should be moved to `tests/` directory (future refactor)

---

## Known Limitations

1. **Single JSON File Storage:** Will become slow with 1000s of entries (migration to Postgres planned)
2. **No Meta-Layer:** Agent evolution/governance not implemented (future enhancement)
3. **Single Partner:** No multi-partner voting (future enhancement)
4. **No Auto-Remediation:** Health monitor detects but doesn't fix (future enhancement)

---

## Future Enhancements

1. **Meta-Layer:** Agent evolution, governance, lifecycle management
2. **Multi-Partner Voting:** Consensus-based decisions
3. **Postgres Migration:** Replace JSON files with database
4. **Auto-Remediation:** Health monitor fixes issues automatically
5. **Integration Tests:** Full pipeline tests in `tests/` directory

---

## Deployment

**Requirements:**
- Python 3.8+
- OpenAI API key
- Environment variables configured

**Run:**
```bash
python run_system.py
```

**Environment Variables:**
- `OPENAI_API_KEY`: Required
- `STORAGE_PATH`: Optional (default: `data/discoveries.json`)
- `SCOUT_INTERVAL_SECONDS`: Optional (default: 300)
- `REVIEWER_INTERVAL_SECONDS`: Optional (default: 60)
- `PARTNER_INTERVAL_SECONDS`: Optional (default: 30)
- `SCOUT_MODEL`: Optional (default: `gpt-5-nano`)
- `REVIEWER_MODEL`: Optional (default: `gpt-5-nano`)
- `PARTNER_USE_LLM`: Optional (default: `true`)
- `PORTFOLIO_DIR`: Optional (default: `data/portfolio`)

---

## Maintenance

**Logging:** All layers use structured logging with agent identity labels

**Error Handling:** Graceful degradation, continues running after errors

**File Safety:** Thread-safe operations, atomic writes, file locking

**Monitoring:** Health monitor detects drift, duplicates, inactivity
