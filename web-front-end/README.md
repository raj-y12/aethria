# Aethria Website

Public-facing website for Aethria, featuring the waiting list and institutional landing pages.

## Design Philosophy

- **Editorial & Architectural**: Abstract.com-inspired spatial layout with layered, angled planes
- **Institutional Minimalism**: Calm, upper-echelon aesthetic
- **Restrained Palette**: #002147 (oxford), #2f333b (graphite), #fcfcfc/#f8f9fb/#f2f4f8/#fafbfc (canvas/mist tones)
- **Typography**: Libre Baskerville (serif) for brand and statements, Inter (sans) for body

## Development

```bash
npm install
npm run dev
```

Runs on `http://localhost:3001`

## Structure

- `src/WaitingListPage.tsx` - Main waiting list page with angled planes layout
- `src/index.css` - Institutional design system styles
- No routing library - single page app

## Key Features

- Full-viewport angled planes creating architectural depth
- Asymmetric layout (not grid-based)
- Embedded form (no card UI)
- Navigation and footer positioned absolutely on planes
- Content column "placed" not mechanically centered
