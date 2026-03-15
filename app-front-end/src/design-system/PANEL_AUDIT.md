# Pass 4 — Panel shell audit

## Shared structural elements

- **Header strip:** flex, items-center, justify-between, border-b border-oxford/[0.06]
- **Section label (title):** left side of header; label style
- **Right-aligned action slot:** Close button and/or Save / Download PDF
- **Tab bar (when present):** flex, gap-0, border-b border-oxford/[0.06], px-4; buttons with border-b-2 active indicator
- **Content area:** flex-1 min-h-0, overflow-y-auto or overflow-hidden with padded inner content
- **Border treatment:** border-oxford/[0.06] for panel borders and header/tab separators

## Differences (to normalise)

| Element | MainLayout right panel | MainLayout mobile overlay | SystemIntelligence | SettingsPage |
|--------|-------------------------|---------------------------|--------------------|--------------|
| Header padding | px-6 py-4 | p-4 sm:p-5 | (no header; parent provides) | px-4 sm:px-6 py-4 |
| Header title class | type-label-tab text-oxford/60 | type-label-section text-oxford/60 | — | type-label-tab text-oxford/60 |
| Close control | type-label-tab "Close" | type-body "×" min-w-[44px] | — | — |
| Tab bar padding | — | — | px-4, py-3 px-3 | px-4, py-3 px-3 |
| Tab label class | — | — | type-label-section | type-label-section |
| Tab inactive | — | — | text-oxford/40 hover:text-oxford/60 | text-oxford/60 hover:text-oxford |
| Tab active | — | — | text-oxford border-oxford | text-oxford border-oxford |
| Content padding | memo: px-6 sm:px-8 py-6; System/Feed: 0 | (child) | p-4 | p-4 sm:p-6 |

## Canonical panel shell spec

- **Header:** height consistent (py-4), padding px-6 (or px-4 sm:px-6 for responsive), border-b border-oxford/[0.06]. Title: type-label-tab text-oxford/60. Action slot: right, same label style for text buttons.
- **Tab bar:** height from py-3, px-4, border-b border-oxford/[0.06]. Tabs: type-label-tab; active: text-oxford border-b-2 border-oxford; inactive: text-oxford/60 border-b-2 border-transparent hover:text-oxford.
- **Content:** flex-1 min-h-0 overflow; inner padding p-4 sm:p-6 (single standard).
