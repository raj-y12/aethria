# Google for Startups Cloud — reapplication readiness audit

**Date:** 2026-08-12 · **Verdict: NOT ready to reapply.** One of the three
rejection criteria remains fully open, and the criterion we *did* fix is not
deployed.

Everything below was verified against the live site and the working tree, not
inferred. Where a claim is unverified it says so.

---

## Criterion 1 — Accessible / unrestricted domain

**PASS.** `https://aethria.co` loads, returns content, is not behind a staging
gate or login wall, and is not an "under construction" page. No action needed.

---

## Criterion 2 — "Incomplete Product Frameworks" (the real blocker)

> Declined if: *marketing sites that only feature "Request a Demo", "Join
> Waitlist", or "Beta Access" buttons without showcasing a live, launched
> product interface.*

**FAIL — and this is the one that will get a second application declined.**

Evidence gathered from the live site:

| Check | Result |
|---|---|
| `aethria.co/v1` (operator console) | Redirects to `/`. The console is **not served from the domain**. |
| Sign-in / log-in link anywhere on the site | **None.** Live nav is only `Index`, `Access`. |
| Calls to action present | `Request access` (waitlist form) and `View the system` — the latter is an **in-page anchor** to a dotted map, not a product. |
| Self-serve sign-up in the app codebase | **Does not exist.** Zero `signUp` / `useSignUp` references in `app-front-end/src`. Accounts are provisioned manually — i.e. invite-only. |
| What a reviewer sees as "the product" | `RecordPlate` — a typographic specimen of a **fictional** company ("Meridian Compute"). It is editorial illustration, not product UI. |

A reviewer landing on aethria.co today sees a beautiful marketing scroll, an
invented example record, and a waitlist form. That is precisely the pattern the
criterion names. **Reapplying without changing this will almost certainly be
declined again.**

`web-front-end/vercel.json` rewrites `/((?!api/).*)` → `index.html`, so the
marketing SPA swallows every path. The operator console is a separate
deployment and is not mounted on this domain.

---

## Criterion 3 — Operational transparency (founder / team)

> Declined if: sites *fail to display authentic founder and core team
> information that is fully verifiable via active, third-party public links
> directly on the domain.*

**FAIL on the live site — fixed locally, but not shipped.**

- `aethria.co/team` **redirects to `/`**. There is no team page in production.
- No founder name, no LinkedIn, no GitHub anywhere on the live domain.
- The live footer and clock still read **"London · San Francisco"**, which is
  factually wrong — the company is Dublin-based.

The team page (founder record, LinkedIn + GitHub, Dublin, founded 2026,
contact email, house tenets) exists **only in the working tree**. `git status`
shows `TeamPage.tsx`, `AccessModal.tsx` and `GithubActivityGrid.tsx` as
untracked, plus eleven modified files. None of it is committed or deployed.

---

## What is missing, ranked

### 1. A reachable, live product interface (blocker)

Ranked by strength of signal against Google's wording:

**(a) Public read-only demo — strongest, and cheapest here.**
`app-front-end/vite.screenshot.config.ts` already renders the **real** console
pages against mock data with Clerk stubbed out — no auth, no backend
(`/screenshot/index.html?route=/v1/flow`). This harness exists and works. Built
and mounted at something like `aethria.co/demo`, it puts a genuine, launched
product interface on the domain with no login wall — answering criteria 1 and 2
simultaneously.

**(b) A product tour section on the marketing site** using real UI captures
from that same harness. Weaker than (a) — static images are still "showcasing"
rather than a live interface — but far better than the fictional specimen
record.

**(c) Open self-serve sign-up.** Strongest possible signal ("launched"), but the
largest lift: no sign-up UI exists at all, and it changes the product's
go-to-market posture from invite-only. Not recommended purely to satisfy a
credits application.

### 2. Ship the team page (blocker, but already built)

Commit and deploy the working tree. Closes criterion 3 outright.

### 3. Correct the location

Live site still claims London · San Francisco. Fixed locally; ships with the
above. Leaving a factually wrong HQ on a page being reviewed for *operational
transparency* is an unnecessary risk.

---

## Recommended sequence

1. Commit and deploy the current `web-front-end` work → criterion 3 closed,
   location corrected.
2. Build and deploy the screenshot harness as a public `/demo` route, linked
   from the primary nav → criterion 2 closed.
3. Re-verify all three criteria against the **live** domain, not localhost.
4. Reapply at the official portal.

## Notes and risks

- The rejection email is notification-only; replies are not routed. There is no
  appeal — only resubmission.
- The stealth-mode alternate path in the email requires **institutional VC
  funding**. Unverified whether that applies here; if it does, the Sales
  contact route bypasses this checklist entirely.
- Option (a) must ship with clearly mocked data. Presenting fabricated
  investment records as real customer activity would be its own problem.
