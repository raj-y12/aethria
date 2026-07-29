# Dispatch Candidate Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an on-demand lookup resolves to multiple genuinely distinct companies (same name / different domain extensions like `.ie` `.com` `.co`), show the analyst an inline candidate picker in the dispatch surface, let them choose (or refine with a website), and only then run the LLM pipeline on the chosen company.

**Architecture:** Add a cheap, synchronous, LLM-free resolve step. The resolver gains a first-class list of distinct candidates grouped by registrable domain. A new `POST /api/startups/lookup/resolve` endpoint runs only the resolver and returns `resolved | ambiguous | not_found`. The frontend's `submit()` calls resolve first; ambiguous results render a picker inline (no navigation); selecting a candidate calls the existing `POST /api/startups/lookup` queue with the chosen website as a hint, so the expensive scout → reviewer → partner path is unchanged. If resolve errors, the frontend falls back to today's direct-queue flow.

**Tech Stack:** Python / FastAPI / Pydantic (backend), pytest with monkeypatched retrieval (backend tests), React + TanStack Query + Framer Motion + Tailwind editorial design system (frontend), TypeScript `tsc` + ESLint (frontend verification — no unit-test runner in this project).

**Design spec:** `docs/superpowers/specs/2026-06-14-dispatch-candidate-disambiguation-design.md`

---

## File Structure

**Backend**
- `backend/resolver/company_resolver.py` — add `CompanyCandidate` model, `candidates` field on `CompanyResolution`, `_build_candidates()` helper, and call it in `resolve_company()`.
- `backend/api.py` — add `POST /api/startups/lookup/resolve` endpoint + a small `_resolve_status_for()` helper.
- `backend/tests/test_company_resolver.py` — candidate-building tests.
- `backend/tests/test_lookup_dispatch.py` — endpoint status-classification tests.

**Frontend**
- `app-front-end/src/api/startups.ts` — add `resolveLookupCandidates()` client + `LookupCandidate` / `LookupResolveResult` types.
- `app-front-end/src/hooks/useDispatchLookup.ts` — resolve-first flow, candidate state, pick + refine handlers, fail-safe.
- `app-front-end/src/components/CandidatePicker.tsx` — new inline picker component (cards + "None of these" refine input).
- `app-front-end/src/components/AgentDispatch.tsx` — render `CandidatePicker` when candidates are present.
- `app-front-end/src/components/DispatchCommandBar.tsx` — pass candidate props through to `AgentDispatch`.

---

## TASK 1: `CompanyCandidate` model + `candidates` field

**Files:**
- Modify: `backend/resolver/company_resolver.py` (after `AlternativeMatch`, ~line 190; and `CompanyResolution` fields ~line 221)

- [ ] **Step 1: Add the `CompanyCandidate` model**

In `backend/resolver/company_resolver.py`, immediately after the `AlternativeMatch` class (ends ~line 190), add:

```python
class CompanyCandidate(BaseModel):
    """A distinct company-owned entity the typed name could refer to.

    Used by the dispatch disambiguation picker: each candidate is one
    registrable domain (so foo.ie and foo.com are separate companies).
    """

    name: str
    website: str
    description: str = ""
    confidence: float = 0.0
    source_badges: List[str] = Field(default_factory=list)
```

- [ ] **Step 2: Add the `candidates` field to `CompanyResolution`**

In the `CompanyResolution` model, add this field next to `alternative_matches` (~line 221):

```python
    candidates: List[CompanyCandidate] = Field(default_factory=list)
```

- [ ] **Step 3: Verify it imports**

Run: `cd /Users/rajyendamuri/aethria && python -c "from backend.resolver.company_resolver import CompanyCandidate, CompanyResolution; print(CompanyResolution().candidates)"`
Expected: prints `[]` with no import error.

> Note: if that import path fails, the test suite runs from `backend/` as the root (imports are `import resolver.company_resolver as cr`). Use: `cd backend && python -c "from resolver.company_resolver import CompanyCandidate; print('ok')"` → prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/resolver/company_resolver.py
git commit -m "feat(resolver): add CompanyCandidate model and candidates field"
```

---

## TASK 2: Build distinct candidates from evidence

**Files:**
- Modify: `backend/resolver/company_resolver.py` (add `_build_candidates`; call it in `resolve_company`)
- Test: `backend/tests/test_company_resolver.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_company_resolver.py`:

```python
def test_distinct_domain_extensions_become_separate_candidates(monkeypatch):
    sources = [
        {
            "title": "Lyra — Irish fintech",
            "url": "https://lyra.ie",
            "snippet": "Lyra is a Dublin-based payments startup for SMEs.",
        },
        {
            "title": "Lyra — US analytics",
            "url": "https://lyra.com",
            "snippet": "Lyra builds healthcare analytics software in San Francisco.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Lyra", user_id=USER)
    domains = {c.website for c in res.candidates}
    assert "https://lyra.ie" in domains
    assert "https://lyra.com" in domains
    assert len(res.candidates) >= 2
    for c in res.candidates:
        assert c.description  # each snapshot has a one-line description


def test_single_clear_company_yields_one_candidate(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics — Home",
            "url": "https://acmerobotics.com",
            "snippet": "Acme Robotics builds warehouse automation robots.",
        },
        {
            "title": "Acme Robotics | LinkedIn",
            "url": "https://www.linkedin.com/company/acme-robotics",
            "snippet": "Acme Robotics. Robotics. 11-50 employees.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Acme Robotics", user_id=USER)
    company_domains = {c.website for c in res.candidates}
    assert company_domains == {"https://acmerobotics.com"}


def test_website_hint_collapses_to_single_candidate(monkeypatch):
    sources = [
        {"title": "Lyra IE", "url": "https://lyra.ie", "snippet": "Dublin payments startup."},
        {"title": "Lyra US", "url": "https://lyra.com", "snippet": "US healthcare analytics."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Lyra", user_id=USER, website_hint="lyra.ie")
    assert res.website == "https://lyra.ie"
    assert [c.website for c in res.candidates] == ["https://lyra.ie"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/rajyendamuri/aethria/backend && python -m pytest tests/test_company_resolver.py -k "candidate or domain_extensions or website_hint_collapses" -v`
Expected: FAIL — `res.candidates` is empty (`[]`), assertions on domains fail.

- [ ] **Step 3: Implement `_build_candidates`**

In `backend/resolver/company_resolver.py`, add this helper just above `def resolve_company(` (~line 580). It groups company-owned domains (skips platform/news hosts), one candidate per registrable domain:

```python
def _friendly_badge(source_type: str) -> Optional[str]:
    return {
        "official_site": "official",
        "linkedin": "linkedin",
        "crunchbase": "crunchbase",
        "dealroom": "dealroom",
        "yc": "yc",
        "news": "news",
    }.get(source_type)


def _build_candidates(
    resolution: CompanyResolution,
    company: str,
    *,
    website_hint: Optional[str],
) -> List[CompanyCandidate]:
    """Group scored evidence into distinct company-owned domains.

    Different registrable domains (lyra.ie vs lyra.com) are different companies,
    so each becomes its own candidate with the best snippet on that domain.
    Platform (LinkedIn/Crunchbase/...) and news hosts are never candidates —
    they are evidence ABOUT a company, not the company's own site.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    for s in resolution.evidence_sources:
        host = _host_of(s.url)
        reg = registrable_domain(host)
        if not reg or reg in _PLATFORM_REGISTRABLE_DOMAINS or reg in _NEWS_REGISTRABLE_DOMAINS:
            continue
        sim = _slug_similarity(company, host)
        # Only domains that plausibly match the typed name are candidates.
        if sim < 0.55 and s.match_score < 0.55:
            continue
        g = groups.setdefault(reg, {"best": s, "score": s.match_score, "badges": set()})
        if s.match_score > g["score"]:
            g["best"] = s
            g["score"] = s.match_score
        badge = _friendly_badge(s.source_type)
        if badge:
            g["badges"].add(badge)

    candidates: List[CompanyCandidate] = []
    for reg, g in groups.items():
        best: EvidenceSource = g["best"]
        candidates.append(
            CompanyCandidate(
                name=reg.split(".", 1)[0],
                website=f"https://{reg}",
                description=(best.snippet or best.title or "")[:200],
                confidence=round(float(g["score"]), 3),
                source_badges=sorted(g["badges"] or {"official"}),
            )
        )

    # A user-provided website hint pins exactly one company.
    if website_hint:
        anchor = registrable_domain(hostname_from_user_hint(website_hint) or "")
        if anchor:
            pinned = [c for c in candidates if registrable_domain(_host_of(c.website)) == anchor]
            if pinned:
                return pinned[:1]
            return [
                CompanyCandidate(
                    name=anchor.split(".", 1)[0],
                    website=f"https://{anchor}",
                    description=(resolution.description or "")[:200],
                    confidence=max(resolution.confidence, 0.6),
                    source_badges=["official"],
                )
            ]

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:5]
```

- [ ] **Step 4: Call `_build_candidates` in `resolve_company`**

In `resolve_company`, after the line `resolution.resolution_status = _assign_status(resolution, website_hint=website_hint)` (~line 675), add:

```python
    resolution.candidates = _build_candidates(resolution, company, website_hint=website_hint)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/rajyendamuri/aethria/backend && python -m pytest tests/test_company_resolver.py -v`
Expected: PASS — all new candidate tests pass and the pre-existing resolver tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/resolver/company_resolver.py backend/tests/test_company_resolver.py
git commit -m "feat(resolver): build distinct company candidates grouped by domain"
```

---

## TASK 3: Resolve endpoint `POST /api/startups/lookup/resolve`

**Files:**
- Modify: `backend/api.py` (add helper + endpoint near the lookup endpoint, ~line 3053)
- Test: `backend/tests/test_lookup_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_lookup_dispatch.py`:

```python
from api import _resolve_status_for
from resolver.company_resolver import CompanyCandidate, CompanyResolution


def _res(status, candidates):
    return CompanyResolution(
        query="x", canonical_name="x", resolution_status=status, candidates=candidates
    )


def test_resolve_status_ambiguous_when_two_strong_candidates():
    res = _res(
        "NEEDS_REVIEW",
        [
            CompanyCandidate(name="lyra", website="https://lyra.ie", confidence=0.9),
            CompanyCandidate(name="lyra", website="https://lyra.com", confidence=0.85),
        ],
    )
    assert _resolve_status_for(res, website_hint=None) == "ambiguous"


def test_resolve_status_resolved_with_single_candidate():
    res = _res("FOUND", [CompanyCandidate(name="acme", website="https://acme.com", confidence=0.9)])
    assert _resolve_status_for(res, website_hint=None) == "resolved"


def test_resolve_status_resolved_when_website_hint_given():
    res = _res(
        "NEEDS_REVIEW",
        [
            CompanyCandidate(name="lyra", website="https://lyra.ie", confidence=0.9),
            CompanyCandidate(name="lyra", website="https://lyra.com", confidence=0.85),
        ],
    )
    assert _resolve_status_for(res, website_hint="lyra.ie") == "resolved"


def test_resolve_status_not_found_when_no_candidates():
    res = _res("NOT_FOUND", [])
    assert _resolve_status_for(res, website_hint=None) == "not_found"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/rajyendamuri/aethria/backend && python -m pytest tests/test_lookup_dispatch.py -k resolve_status -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_status_for'`.

- [ ] **Step 3: Implement the status helper + endpoint**

In `backend/api.py`, add the helper and endpoint immediately after the `lookup_startup` function (after its closing, ~line 3115). The endpoint reuses `_parse_lookup_input`, `require_authenticated_user`, the `_LOOKUP_*` rate-limit policies, and calls `resolve_company` off the event loop:

```python
_AMBIGUOUS_MIN_CONFIDENCE = 0.7


def _resolve_status_for(resolution, website_hint: Optional[str]) -> str:
    """Classify a resolution for the dispatch picker: resolved | ambiguous | not_found."""
    candidates = list(getattr(resolution, "candidates", []) or [])
    if resolution.resolution_status == "NOT_FOUND" or not candidates:
        return "not_found"
    if (website_hint or "").strip():
        return "resolved"
    strong = sum(1 for c in candidates if c.confidence >= _AMBIGUOUS_MIN_CONFIDENCE)
    if strong >= 2:
        return "ambiguous"
    return "resolved"


@app.post("/api/startups/lookup/resolve")
async def resolve_lookup_candidates(request: Request, body: Dict[str, Any]):
    """Cheap, synchronous, LLM-free identity resolution for the dispatch picker.

    Body: {"lookup_input": "...", "website_hint": optional}. Returns the distinct
    company candidates the typed name could mean WITHOUT running scout/reviewer/partner.
    """
    from resolver.company_resolver import resolve_company

    lookup_input = str(body.get("lookup_input") or body.get("company_name") or "").strip()
    if not lookup_input:
        raise HTTPException(status_code=422, detail="lookup_input is required")
    if len(lookup_input) > 300:
        raise HTTPException(status_code=422, detail="lookup_input is too long")
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(
        f"user:{user_id}:lookup", [_LOOKUP_MINUTE_POLICY, _LOOKUP_DAY_POLICY]
    )
    if limited is not None:
        return limited

    parsed = _parse_lookup_input(lookup_input)
    company_name = str(parsed.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Could not derive company name from lookup_input")
    website_hint = str(body.get("website_hint") or parsed.get("website") or "").strip() or None

    loop = asyncio.get_event_loop()
    resolution = await loop.run_in_executor(
        None,
        partial(resolve_company, company_name, user_id=user_id, website_hint=website_hint),
    )
    status = _resolve_status_for(resolution, website_hint=website_hint)
    candidates = [c.model_dump(mode="json") for c in resolution.candidates]
    return JSONResponse(
        status_code=200,
        content={
            "status": status,
            "canonical_name": resolution.canonical_name,
            "company_name": company_name,
            "website_hint": website_hint,
            "candidates": candidates if status != "resolved" else candidates[:1],
        },
    )
```

- [ ] **Step 4: Confirm `partial` and `asyncio` are imported in `api.py`**

Run: `cd /Users/rajyendamuri/aethria/backend && python -c "import api" && grep -nE "^import asyncio|from functools import partial" api.py`
Expected: prints both import lines. If `from functools import partial` is missing, add it near the top imports of `api.py` and re-run.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/rajyendamuri/aethria/backend && python -m pytest tests/test_lookup_dispatch.py -v`
Expected: PASS — all status tests pass; existing parse tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api.py backend/tests/test_lookup_dispatch.py
git commit -m "feat(api): add lookup/resolve endpoint for candidate disambiguation"
```

---

## TASK 4: Frontend API client + types

**Files:**
- Modify: `app-front-end/src/api/startups.ts`

- [ ] **Step 1: Add the candidate types and client**

In `app-front-end/src/api/startups.ts`, after the `queueOnDemandLookup` function (~line 165), add:

```typescript
export interface LookupCandidate {
  name: string;
  website: string;
  description: string;
  confidence: number;
  source_badges: string[];
}

export type LookupResolveStatus = 'resolved' | 'ambiguous' | 'not_found';

export interface LookupResolveResult {
  status: LookupResolveStatus;
  canonicalName: string;
  companyName: string;
  websiteHint: string | null;
  candidates: LookupCandidate[];
}

/**
 * Cheap pre-flight: resolve a typed name into distinct company candidates
 * (LLM-free). Drives the dispatch disambiguation picker before we queue the
 * expensive scout/reviewer/partner pipeline.
 */
export async function resolveLookupCandidates(
  lookupInput: string,
  websiteHint?: string,
): Promise<LookupResolveResult> {
  const input = lookupInput.trim();
  if (!input) throw new Error('lookupInput is required');
  const res = await authedFetch(`${API_BASE}/api/startups/lookup/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ lookup_input: input, website_hint: websiteHint?.trim() || undefined }),
  });
  if (!res.ok) throw new Error(`Resolve API error: ${res.status}`);
  const data = await res.json();
  const candidates: LookupCandidate[] = Array.isArray(data?.candidates)
    ? data.candidates.map((c: Record<string, unknown>) => ({
        name: String(c?.name ?? ''),
        website: String(c?.website ?? ''),
        description: String(c?.description ?? ''),
        confidence: typeof c?.confidence === 'number' ? c.confidence : 0,
        source_badges: Array.isArray(c?.source_badges) ? (c.source_badges as string[]) : [],
      }))
    : [];
  const status: LookupResolveStatus =
    data?.status === 'ambiguous' || data?.status === 'not_found' ? data.status : 'resolved';
  return {
    status,
    canonicalName: String(data?.canonical_name ?? input),
    companyName: String(data?.company_name ?? input),
    websiteHint: typeof data?.website_hint === 'string' ? data.website_hint : null,
    candidates,
  };
}
```

- [ ] **Step 2: Type-check**

Run: `cd /Users/rajyendamuri/aethria/app-front-end && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add app-front-end/src/api/startups.ts
git commit -m "feat(front): resolveLookupCandidates client + candidate types"
```

---

## TASK 5: CandidatePicker component

**Files:**
- Create: `app-front-end/src/components/CandidatePicker.tsx`

- [ ] **Step 1: Create the component**

Create `app-front-end/src/components/CandidatePicker.tsx`. Inline picker (no modal/route): one card per candidate showing name, domain with extension, description, badges; plus a "None of these" website refine input. Styling matches the editorial system used by `AgentDispatch` (`text-oxford`, `type-meta`, `productInteraction`); Framer Motion for the reveal.

```typescript
import { useState, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import type { LookupCandidate } from '../api/startups';
import { productInteraction } from '../design-system/productSystem';

interface CandidatePickerProps {
  candidates: LookupCandidate[];
  onPick: (candidate: LookupCandidate) => void;
  onRefine: (websiteHint: string) => void;
  busy?: boolean;
}

/** Strip protocol so the registrable domain (and its .ie/.com/.co extension) reads cleanly. */
function domainLabel(website: string): string {
  return website.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

export default function CandidatePicker({ candidates, onPick, onRefine, busy }: CandidatePickerProps) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [website, setWebsite] = useState('');

  const submitRefine = () => {
    const value = website.trim();
    if (value) onRefine(value);
  };
  const onWebsiteKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submitRefine();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="mt-phi-3 grid gap-phi-2"
      aria-label="Select the company you meant"
    >
      <p className="type-meta text-oxford/[0.45]">
        More than one company matches — select the one you meant.
      </p>

      {candidates.map((c) => (
        <button
          key={c.website}
          type="button"
          disabled={busy}
          onClick={() => onPick(c)}
          className="group w-full text-left border border-oxford/[0.10] hover:border-oxford/[0.30] bg-paper px-phi-3 py-phi-3 transition-colors disabled:opacity-60 btn-interaction"
        >
          <div className="flex items-baseline justify-between gap-phi-2">
            <span className="font-sans font-medium text-[13px] text-oxford truncate">{c.name}</span>
            <span className="type-meta text-oxford/[0.50] shrink-0">{domainLabel(c.website)}</span>
          </div>
          {c.description ? (
            <p className="mt-phi-1 type-meta text-oxford/[0.55] line-clamp-2">{c.description}</p>
          ) : null}
          {c.source_badges.length ? (
            <div className="mt-phi-2 flex flex-wrap gap-phi-1">
              {c.source_badges.map((b) => (
                <span
                  key={b}
                  className="type-meta text-oxford/[0.40] border border-oxford/[0.10] px-phi-1 leading-[1.6]"
                >
                  {b}
                </span>
              ))}
            </div>
          ) : null}
        </button>
      ))}

      {refineOpen ? (
        <div className="flex items-center gap-phi-2 border-b border-oxford/[0.18] pt-phi-1">
          <input
            type="text"
            autoFocus
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            onKeyDown={onWebsiteKeyDown}
            placeholder="Company website (e.g. example.ie)"
            autoComplete="off"
            disabled={busy}
            className="min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-2 font-sans text-[13px] text-oxford placeholder:text-oxford/[0.28] outline-none"
          />
          <button type="button" onClick={submitRefine} disabled={busy || !website.trim()} className={productInteraction.action}>
            Resolve →
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setRefineOpen(true)}
          disabled={busy}
          className="justify-self-start type-meta text-oxford/[0.40] hover:text-oxford/[0.70] bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
        >
          None of these — add a website
        </button>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd /Users/rajyendamuri/aethria/app-front-end && npx tsc --noEmit`
Expected: no errors. If `productInteraction.action` is not a string member, open `src/design-system/productSystem.ts`, confirm the export, and use the correct member (the same one `AgentDispatch.tsx` uses in `runBtnCls`).

- [ ] **Step 3: Commit**

```bash
git add app-front-end/src/components/CandidatePicker.tsx
git commit -m "feat(front): inline CandidatePicker for dispatch disambiguation"
```

---

## TASK 6: Resolve-first flow in useDispatchLookup

**Files:**
- Modify: `app-front-end/src/hooks/useDispatchLookup.ts`

- [ ] **Step 1: Import the resolve client and candidate type**

In the import block (~line 4) extend the existing `../api/startups` import to add `resolveLookupCandidates` and `type LookupCandidate`:

```typescript
import {
  cancelOnDemandLookups,
  queueOnDemandLookup,
  fetchStartupDetail,
  fetchLookupJobStatus,
  resolveLookupCandidates,
  type LookupCandidate,
} from '../api/startups';
```

- [ ] **Step 2: Add candidate state**

After the existing `const [message, setMessage] = useState<string | null>(null);` (~line 52), add:

```typescript
  const [candidates, setCandidates] = useState<LookupCandidate[]>([]);
  const [refining, setRefining] = useState(false);
```

- [ ] **Step 3: Extract the queue step and rewrite `submit` to resolve first**

Replace the entire `submit` callback (~lines 63-96) with a `queueLookup` helper plus a resolve-first `submit`. `queueLookup` holds the existing queue logic; `submit` resolves first, queues directly on `resolved`, shows the picker on `ambiguous`, and **falls back to direct queue if resolve throws** (fail-safe per spec):

```typescript
  const queueLookup = useCallback(
    async (value: string, requestSeq: number) => {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      if (requestSeqRef.current !== requestSeq) return;
      const current = pendingLookup;
      if (current && !current.autoOpened && current.lookupId !== queued.lookupId) {
        setBackgroundLookups((bg) => [current, ...bg.filter((l) => l.lookupId !== current.lookupId)]);
      }
      setCandidates([]);
      setRefining(false);
      setPendingLookup({ lookupId: queued.lookupId, queryLabel: value, autoOpened: false });
      setMessage(
        `Lookup queued for ${queued.companyName}. We are now finding and validating the company profile.`,
      );
      setInput('');
    },
    [pendingLookup],
  );

  const submit = useCallback(async () => {
    const value = input.trim();
    if (!value || busy) return;
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setBusy(true);
    setMessage('Confirming the company identity...');
    try {
      let resolved;
      try {
        resolved = await resolveLookupCandidates(value);
      } catch {
        // Fail-safe: resolve outage must not break dispatch — queue directly.
        await queueLookup(value, requestSeq);
        return;
      }
      if (requestSeqRef.current !== requestSeq) return;
      if (resolved.status === 'ambiguous') {
        setCandidates(resolved.candidates);
        setMessage('Multiple companies match — select the one you meant.');
        return;
      }
      if (resolved.status === 'not_found') {
        setCandidates([]);
        setMessage(
          `No clear match for ${value}. Add the company website to pin it (e.g. "${value} example.com").`,
        );
        return;
      }
      const pick = resolved.candidates[0];
      await queueLookup(pick ? `${pick.name} ${pick.website}` : value, requestSeq);
    } catch {
      setMessage('Could not submit lookup request. Please retry in a few seconds.');
    } finally {
      if (requestSeqRef.current === requestSeq) setBusy(false);
    }
  }, [input, busy, queueLookup]);
```

- [ ] **Step 4: Add pick and refine handlers**

Immediately after `submit`, add:

```typescript
  const pickCandidate = useCallback(
    async (candidate: LookupCandidate) => {
      const requestSeq = requestSeqRef.current + 1;
      requestSeqRef.current = requestSeq;
      setBusy(true);
      try {
        await queueLookup(`${candidate.name} ${candidate.website}`, requestSeq);
      } catch {
        setMessage('Could not submit lookup request. Please retry in a few seconds.');
      } finally {
        if (requestSeqRef.current === requestSeq) setBusy(false);
      }
    },
    [queueLookup],
  );

  const refineWithWebsite = useCallback(
    async (websiteHint: string) => {
      const value = input.trim() || websiteHint.trim();
      const requestSeq = requestSeqRef.current + 1;
      requestSeqRef.current = requestSeq;
      setRefining(true);
      setBusy(true);
      try {
        const resolved = await resolveLookupCandidates(value, websiteHint);
        if (requestSeqRef.current !== requestSeq) return;
        if (resolved.status === 'ambiguous') {
          setCandidates(resolved.candidates);
          setMessage('Still more than one match — pick a candidate or refine again.');
          return;
        }
        const pick = resolved.candidates[0];
        await queueLookup(pick ? `${pick.name} ${pick.website}` : `${value} ${websiteHint}`, requestSeq);
      } catch {
        setMessage('Could not resolve that website. Please retry.');
      } finally {
        if (requestSeqRef.current === requestSeq) {
          setBusy(false);
          setRefining(false);
        }
      }
    },
    [input, queueLookup],
  );
```

- [ ] **Step 5: Clear candidates on cancel and expose new values**

In the existing `cancel` callback (~line 98), add `setCandidates([]);` and `setRefining(false);` alongside the other resets. Then in the hook's returned object (~line 333), add:

```typescript
    candidates,
    pickCandidate,
    refineWithWebsite,
    refining,
```

- [ ] **Step 6: Type-check**

Run: `cd /Users/rajyendamuri/aethria/app-front-end && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add app-front-end/src/hooks/useDispatchLookup.ts
git commit -m "feat(front): resolve-first dispatch flow with candidate pick + website refine"
```

---

## TASK 7: Wire the picker into the dispatch surface

**Files:**
- Modify: `app-front-end/src/components/AgentDispatch.tsx`
- Modify: `app-front-end/src/components/DispatchCommandBar.tsx`
- Modify: the call site that renders `DispatchCommandBar` (find via grep in Step 1)

- [ ] **Step 1: Find the render call site**

Run: `cd /Users/rajyendamuri/aethria && rg -n "useDispatchLookup\(|<DispatchCommandBar" app-front-end/src`
Expected: shows the hook usage and where `<DispatchCommandBar .../>` is rendered (note these file paths for Step 4).

- [ ] **Step 2: Accept picker props in `AgentDispatch`**

In `app-front-end/src/components/AgentDispatch.tsx`, add to the imports:

```typescript
import CandidatePicker from './CandidatePicker';
import type { LookupCandidate } from '../api/startups';
```

Extend `AgentDispatchProps` (~line 5) with:

```typescript
  candidates?: LookupCandidate[];
  onPickCandidate?: (candidate: LookupCandidate) => void;
  onRefineWebsite?: (websiteHint: string) => void;
```

Destructure them in the `AgentDispatch` function signature (~line 197), then render the picker right after `<DispatchPanelBody .../>` inside the embedded branch (the `!isDrawer` block, ~line 309) AND inside the drawer branch (~line 334). To avoid duplication, render once just before the component's final closing — add this block immediately after the `DispatchPanelBody` usage in **each** branch:

```typescript
{candidates && candidates.length > 0 && onPickCandidate && onRefineWebsite ? (
  <CandidatePicker
    candidates={candidates}
    onPick={onPickCandidate}
    onRefine={onRefineWebsite}
    busy={isBusy}
  />
) : null}
```

- [ ] **Step 3: Pass props through `DispatchCommandBar`**

In `app-front-end/src/components/DispatchCommandBar.tsx`, add the same three optional props to the component's props interface (near `onSubmit`, ~line 31):

```typescript
  candidates?: LookupCandidate[];
  onPickCandidate?: (candidate: LookupCandidate) => void;
  onRefineWebsite?: (websiteHint: string) => void;
```

Add `import type { LookupCandidate } from '../api/startups';` at the top. Destructure the three props in the `DispatchCommandBar` function, then forward them on the `<AgentDispatch .../>` element (~line 341):

```typescript
                    candidates={candidates}
                    onPickCandidate={onPickCandidate}
                    onRefineWebsite={onRefineWebsite}
```

- [ ] **Step 4: Pass hook values at the render call site**

In the file from Step 1 that renders `<DispatchCommandBar`, pull `candidates`, `pickCandidate`, `refineWithWebsite` from the `useDispatchLookup(...)` return, and pass them to `<DispatchCommandBar`:

```typescript
        candidates={candidates}
        onPickCandidate={pickCandidate}
        onRefineWebsite={refineWithWebsite}
```

- [ ] **Step 5: Type-check and lint**

Run: `cd /Users/rajyendamuri/aethria/app-front-end && npx tsc --noEmit && npm run lint`
Expected: no type errors, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add app-front-end/src/components/AgentDispatch.tsx app-front-end/src/components/DispatchCommandBar.tsx app-front-end/src
git commit -m "feat(front): render candidate picker inline in dispatch surface"
```

---

## TASK 8: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd /Users/rajyendamuri/aethria/backend && python -m pytest tests/test_company_resolver.py tests/test_lookup_dispatch.py -v`
Expected: all PASS.

- [ ] **Step 2: Frontend build**

Run: `cd /Users/rajyendamuri/aethria/app-front-end && npm run build`
Expected: `tsc` + `vite build` succeed with no errors.

- [ ] **Step 3: Preview verification of the picker**

Start the frontend preview, open the dispatch surface, and dispatch an intentionally ambiguous name (one known to have multiple domain extensions, e.g. a short common brand). Confirm:
- The inline picker appears in the dispatch surface (no navigation away).
- Each candidate shows name, domain **with extension**, description, badges.
- Clicking a candidate transitions to the normal "queued / scouting" flow.
- "None of these — add a website" reveals the website input; submitting it pins one company and proceeds.
- With the backend resolve endpoint stopped/erroring, dispatch still works (falls back to direct queue).

Capture a screenshot of the picker for the summary.

- [ ] **Step 4: Final commit (if any verification fixups were needed)**

```bash
git add -A
git commit -m "test: verify dispatch candidate disambiguation end-to-end"
```

---

## Self-Review Notes

- **Spec coverage:** distinct-domain candidates (Task 2) · resolve endpoint with three statuses (Task 3) · inline picker, no navigation (Tasks 5,7) · pick → existing queue with website hint (Task 6) · "None of these" website refine (Tasks 5,6) · fail-safe fallback to direct queue (Task 6 Step 3) · ambiguity-only trigger (Task 3 `_resolve_status_for`) · tests (Tasks 2,3) — all covered.
- **No change to scout/reviewer/partner:** selection reuses `queueOnDemandLookup`, which feeds the existing pipeline via the existing `website_hint` parse path (`_parse_lookup_input` already extracts an embedded domain — verified by `test_parse_lookup_input_keeps_embedded_website_disambiguation`).
- **Type consistency:** `LookupCandidate` shape (name/website/description/confidence/source_badges) is identical across backend `CompanyCandidate`, the `resolveLookupCandidates` client, `CandidatePicker`, and the hook. Handlers named `pickCandidate`/`refineWithWebsite` (hook) map to `onPickCandidate`/`onRefineWebsite` (component props) consistently.
