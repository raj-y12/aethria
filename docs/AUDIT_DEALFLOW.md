# AETHRIA DealFlow OS – Audit Report

Implementation audit: storage, models, adapters, memo generator, wipe script. For product requirements, API, roadmap, and ops summary see **[AETHRIA_PRD_AND_ARTIFACTS.md](AETHRIA_PRD_AND_ARTIFACTS.md)**.

---

## 1. Scope

- **Adapters**: ScoutOutput/ReviewerOutput/PartnerOutput → Pydantic (ScoutInfo, ReviewInfo, PartnerInfo).
- **Memo generator**: Startup → Markdown investment memo.
- **Migration**: discoveries.json → startups.json (Pydantic).
- **Storage**: Thread-safe JSON persistence of Startup records.
- **Models**: ScoutInfo, ReviewInfo, PartnerInfo, Financials, Startup.

---

## 2. Findings and Fixes

### 2.1 Storage

| Item | Status | Notes |
|------|--------|--------|
| Full read/write of Pydantic Startup | OK | `add_startup`, `add_review`, `add_partner_decision`, `update_financials`; `get_startup`, `get_all_startups`. |
| Unreviewed / undecided | OK | `get_unreviewed`, `get_undecided`; now use `skip_invalid=True` by default so one bad record does not break the pipeline. |
| Thread-safe, atomic writes | OK | `_atomic_update` with exclusive lock; write to temp file, fsync, rename. |
| Timestamps on changes | OK | `Startup.update_timestamp()` used in all add/update paths. |
| Reset / wipe | **Added** | `reset_to_empty()` and `replace_all(items)` for wipe and bulk load. |
| Migration bug | **Fixed** | Migration previously called non-existent `_write_file`. It now builds a list and calls `replace_all(migrated)`. |

### 2.2 Models

| Item | Status | Notes |
|------|--------|--------|
| Validation | OK | Pydantic v2; scores 1–10, confidence 0–1, Literal enums. |
| Null timestamps | **Fixed** | `from_dict` now normalizes ISO strings and replaces `null` with `datetime.now()` for required datetimes (created_at, updated_at, discovered_at, reviewed_at, partnered_at). |
| Optional financials | OK | All Financials fields optional; revenue_missing / funding_missing / valuation_missing default False. |
| ISO datetimes | OK | `to_dict()` uses `model_dump(mode='json')`; datetimes serialized as ISO. |

### 2.3 Adapters

| Item | Status | Notes |
|------|--------|--------|
| Empty startup_id | **Fixed** | If ScoutOutput `id` is missing or blank, adapter now uses `uuid4()` so startup_id is never empty. |
| Timestamps | OK | `_parse_timestamp` and fallback to `datetime.now()` for discovered_at, reviewed_at, partnered_at. |
| Legacy decision map | OK | INVEST→YES, WATCH→MAYBE, PASS→NO; conviction_level from confidence. |

### 2.4 Memo Generator

| Item | Status | Notes |
|------|--------|--------|
| Immutability | OK | Does not mutate Startup. |
| Missing financials | OK | Uses [MISSING]; mentions diligence_red_flags when present. |
| Partner next_action / human_review | OK | Surfaces next_action, rationale, MAYBE + human_review_required. |

### 2.5 Backward Compatibility

| Item | Status | Notes |
|------|--------|--------|
| add_discovery(scout_output) | OK | Adapts to ScoutInfo and calls add_startup. |
| get_unreviewed_entries / get_undecided_entries | OK | Return dicts; use same skip_invalid behavior as get_unreviewed / get_undecided. |
| get_all / get_by_id | OK | Return dicts; get_all uses skip_invalid=True. |
| Old discovery format | OK | Migration supports id/startup_id, scout/review/partner, timestamps. |

### 2.6 Meta-Agent / Integration

| Item | Status | Notes |
|------|--------|--------|
| validate_and_parse(raw) | OK | Single entry point to validate dict → Startup. |
| get_startups_with_review | OK | For downstream / Meta-Agent. |
| get_startups_with_decision(decision=YES/NO/MAYBE) | OK | Filter by decision. |
| get_startups_requiring_human_review | OK | human_review_required=True. |
| replace_all / reset_to_empty | OK | Bulk load and wipe for pipelines. |

---

## 3. Fields That May Be Missing and Handling

| Field | Where | Handling |
|-------|--------|----------|
| funding_stage, est_tam | ScoutInfo | Optional; null/omitted allowed; memo shows [MISSING]. |
| defensibility_score | ReviewInfo | Optional; memo shows only if present. |
| diligence_red_flags | ReviewInfo | Default []; Reviewer should populate when data is missing. |
| reviewer_agent_id, partner_agent_id | ReviewInfo, PartnerInfo | Optional; engines set when saving. |
| traction_metrics, funding_history, valuation_est, ip_status | Financials | Optional; memo shows [MISSING] when absent. |
| discovered_at, reviewed_at, partnered_at | Nested | Required on model; from_dict uses now() if null/missing in JSON. |
| created_at, updated_at | Startup | Same; from_dict uses now() if null/missing. |

---

## 4. Wipe Script

**Path**: `backend/scripts/wipe_startups.py`

**Usage**:

```bash
cd backend
python scripts/wipe_startups.py [--path data/startups.json] [--dry-run]
```

**Behavior**:

- Loads `Storage` with given path (default `data/startups.json` or `STORAGE_PATH`).
- Calls `storage.reset_to_empty()` (atomic replace with `[]`).
- Logs count before/after; exit 0 on success, 1 on error.
- `--dry-run`: only logs, no write.

---

## 5. Storage Methods Added / Clarified

```python
# Wipe and re-initialize
storage.reset_to_empty()

# Bulk replace (e.g. after migration or import)
storage.replace_all(list_of_startup_dicts)
```

- `replace_all(items)` checks `items` is a list and runs one `_atomic_update(lambda _: items)`.
- `reset_to_empty()` is `_atomic_update(lambda _: [])`.

---

## 6. Recommendations

1. **Migrations**: Prefer building a full list in memory and calling `replace_all()` once (as in the fixed migration) instead of many small writes.
2. **Meta-Agent**: Use `get_startups_with_review()`, `get_startups_with_decision()`, `get_startups_requiring_human_review()`, and `validate_and_parse()` for consistent, validated inputs.
3. **Consistency**: Keep using `skip_invalid=True` in `get_unreviewed` and `get_undecided` so corrupt entries are skipped and logged instead of failing the pipeline.
4. **Resources**: When wiring agents to `/resources`, validate Scout/Reviewer/Partner outputs against the JSON Schemas in `resources/contracts/schemas` before persisting.
5. **Datetimes**: All datetime fields are set or normalized in `from_dict`; serialization remains ISO via `to_dict()` / `model_dump(mode='json')`.

---

## 7. Summary of Code Changes

- **storage.py**: `replace_all(items)`, `reset_to_empty()`; `get_unreviewed`/`get_undecided` default `skip_invalid=True`.
- **models.py**: `from_dict` copies and normalizes dict; `_normalize_timestamp`; null/missing datetimes → `datetime.now()` for required fields.
- **adapters.py**: `startup_id` from ScoutOutput: if missing or blank, use `str(uuid4())`.
- **migration.py**: Build `migrated` list, then `new_storage.replace_all(migrated)`; removed use of non-existent `_write_file`.
- **scripts/wipe_startups.py**: New script to safely wipe startups.json and initialize empty storage.
