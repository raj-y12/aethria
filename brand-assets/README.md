# Aethria brand assets

Everything here is generated from the logo the marketing site actually renders —
the arrival overlay in `web-front-end` (`src/components/GalleryLoader.tsx` plus
the `GALLERY LOADER` block of `src/index.css`): a Playfair Display 500 wordmark
with a verdigris full stop, held between two hairline brackets.

Open `index.html` in a browser to preview and download everything.

## Regenerating

```bash
python3 brand-assets/scripts/generate_brand_assets.py
python3 brand-assets/scripts/verify_brand_assets.py
```

Requires `fonttools[woff2]`, `uharfbuzz`, `cairosvg` and `pillow`. The generator
reads Playfair Display 500 from `web-front-end/node_modules/@fontsource/` so the
assets and the site can never disagree about the typeface; run `npm ci` in
`web-front-end` first, or pass `--font <path to the woff2>`.

Both scripts are safe to re-run — output is deterministic.

## How the lockup is derived

Geometry comes from the stylesheet, not from eyeballing a screenshot. At the
reference `font-size` of 64px:

| Property | Value | Source |
|---|---|---|
| Wordmark advance | 231.046875px | measured in Chromium |
| Line box | 96px (1.5x) | Tailwind v3 preflight `html { line-height: 1.5 }` |
| Bracket width | 14px | `.gallery-loader-mark::before` |
| Bracket overhang | 14px top and bottom | `top: -14px; bottom: -14px` |
| Bracket gap | 12px | `left: -26px` minus the 14px width |
| Bracket stroke | 1px | `border: 1px solid var(--line-2)` |

Everything is stored as a ratio of the font size, so the lockup scales without
drift. `generate_brand_assets.py` asserts on every run that HarfBuzz shapes
`Aethria.` to the same advance Chromium measured; if the font file or the
shaping settings ever change, generation fails rather than silently shipping a
different logo.

Two properties make these usable as brand assets rather than screenshots:

- **Glyphs are outlined to paths.** Nothing depends on Playfair Display being
  installed, so an SVG opened in Figma, Illustrator, Slides or a browser is the
  same shape every time. `verify_brand_assets.py` fails if any SVG regains a
  `font-family`.
- **Text is shaped with HarfBuzz**, the same engine the browser uses, so kerning
  matches the site exactly.

## Palette

Taken from `web-front-end/src/index.css`. Earlier assets had drifted onto three
different navies (`#001433`, `#1A2B48`, `#1D2D48`), none of which the site used.

| Token | Hex | Role |
|---|---|---|
| `--ink` / `--color-oxford` | `#0a1629` | Wordmark on light, background on dark |
| `--stock` | `#d9d7d4` | Background on light, wordmark on dark |
| `--accent` / `--color-brand-mark` | `#3d6b5e` | The full stop, on light |
| `--color-brand-mark-inverse` | `#7aab9a` | The full stop, on dark — verdigris is too dark on navy |

Bracket hairlines are the foreground colour at 26% opacity (`--line-2`).

## What to use where

**Vector masters** (`assets/*.svg`) — use these anywhere a vector is accepted.

| File | Use |
|---|---|
| `logo-lockup-{light,dark}.svg` | **Primary logo.** The bracketed wordmark on its own ground |
| `logo-lockup-{transparent,inverse-transparent}.svg` | Primary logo over an existing background |
| `logo-wordmark-*.svg` | No brackets — for tight spaces where they would crowd |
| `logo-monogram-*.svg` | Square `A.` for avatars and app icons |
| `logo-monogram-framed-*.svg` | Bracketed square mark — **256px and above only** |
| `favicon.svg`, `logo-icon-*.svg` | 32px marks; `favicon.svg` is mirrored into both frontends' `public/` |

Clear space is baked into every master at half a cap height. Do not crop it off.

**Google Workspace** (`assets/google-workspace/`) — exact-size PNGs, upload
as-is, never resize:

| File | Slot |
|---|---|
| `workspace-admin-logo-320x132-{light,dark}.png` | Admin console company logo (displayed at exactly 320x132, 30 KB ceiling — these are ~9 KB) |
| `workspace-app-logo-120x120.png` | OAuth consent screen app logo (square, 120px minimum) |
| `workspace-app-logo-{256,512,1024}.png` | App identity where a larger square is accepted |
| `workspace-avatar-256x256.png` | Google Chat app / profile avatar |
| `marketplace-icon-{32,48,96,128}.png` | Marketplace store listing application icons |
| `marketplace-tile-220x140.png` | Marketplace card banner |
| `marketplace-tile-440x280.png` | Marketplace large promotional tile |
| `marketplace-marquee-1400x560.png` | Marketplace marquee |
| `lockup-2048-{transparent,inverse-transparent}.png` | Docs, Slides and decks — alpha preserved |

Use the **dark** variants by default; the navy ground is what makes the mark
read against Google's white chrome.

The Marketplace listing also takes 1280x800 screenshots. Those are product
captures, not brand assets, so they are deliberately not generated here.

`assets/MANIFEST.json` lists every generated file with its dimensions.

### Sources for the Workspace constraints

- [Add your logo to Google Workspace](https://support.google.com/a/answer/96474) — 320x132, PNG or GIF, 30 KB maximum
- [Manage OAuth App Branding](https://support.google.com/cloud/answer/15549049) — square app logo, 120x120 minimum
- [Create a store listing](https://developers.google.com/workspace/marketplace/create-listing) — Marketplace icon and promotional artwork sizes

## Not generated here

`aethria_motion_blur_hero_4k.png` is a presentation background produced by
`scripts/generate_motion_blur_hero.py`, which is unrelated to the logo pipeline.
