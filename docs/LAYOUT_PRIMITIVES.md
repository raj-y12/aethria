# Layout Primitives

Use these across Aethria pages for consistent, institutional layout.

- **PageWrapper** — Full-width shell. `variant`: `ivory` | `mist`. Header, footer, hero = full width.
- **Section** — Vertical rhythm. `spacing`: `none` | `sm` | `md` | `lg`. Optional `dividerBelow`.
- **Divider** — Soft horizontal line (`charcoal/10`). `fullWidth` (default) or content-bound.
- **ContentColumn** — Max-width by use. `variant`: `content` (80%, editorial) | `reading` (42rem) | `panel` (wide instrument layout).

**Width rules:** Content width does *not* apply to the main decision feed, system bars, judgement annotations, or temporal indicators. Use `panel` for the operational feed; system bar and clock are full-width.

**Location:** `app-front-end/src/layout/`
