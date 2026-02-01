# Aethria Design Constitution

Decision intelligence system. Calm, cold, precise, institutional. Not marketing, not SaaS.

## Locked palette (no new colors)

| Token   | Hex     | Use |
|---------|---------|-----|
| oxford  | #002147 | Structural: dividers, rules, active states, key anchors. |
| charcoal| #2f333b | Primary text, structure. |
| ivory   | #fcfcfc | Main canvas (off-white). |
| bone    | #f2f4f8 | Secondary planes, separators (soft bone). |

No gradients. No hard color blocks. Use spacing, opacity, thin rules instead of containers.

## Typography (strict)

- **Libre Baskerville** → ONLY: "Aethria" wordmark (Enter page + subtle app seal).
- **Inter** (sans) → All headings and body text.
- Hierarchy via size, weight, spacing — not color.

## Layout

- No cards, no boxed UI, no rounded panels, no clutter.
- Vertical rhythm and thin dividers (`border-oxford` at low opacity) for section rules.
- **max-width 80%** for editorial content; wider for operational feed.
- Headers, system bars, clock, status = full-width.

## System elements

- **Aethria wordmark** — Top-left in app. Libre Baskerville, subdued. System seal, not logo.
- **Global Clock** — Top-center. Temporal anchor. Clean, understated, always visible.
- **System Status / Scout Count** — Instrumentation. Subtle, restrained, legible. No flashing.

## Preserved (do not change)

- **Enter System** page (HomePage) and **loading / scanning** animation. Refine spacing, typography, or alignment only — not conceptual role.

## Primitives

Layout primitives live in `app-front-end/src/layout/`: `PageWrapper`, `Section`, `Divider`, `ContentColumn`. Use for structure; keep UI minimal. See [LAYOUT_PRIMITIVES.md](LAYOUT_PRIMITIVES.md).
