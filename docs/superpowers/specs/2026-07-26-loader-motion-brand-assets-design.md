# Loader Motion Brand Assets — Design

## Goal

Bring the downloadable Aethria brand assets and banner studio into alignment with the marketing site's gallery-loader: a bracketed `Aethria.` wordmark on a cool stock background, with verdigris punctuation and an editorial instrument-panel feel.

## Visual direction

- **Primary mark:** `Aethria.` in Playfair Display, set within two thin open brackets. The wordmark is dark ink on stock/light surfaces and stock on deep-ink surfaces; the full stop is verdigris.
- **Small marks:** Monogram, icon, transparent icon, and favicon retain the letter `A` for legibility at small sizes, but replace the previous solid-square treatment with the same open bracket geometry and palette.
- **Motion field:** Banners replace the current radial-gradient mesh with a dense, near-horizontal photographic motion-blur field. Overlapping broad soft bands and fine streaks run left-to-right across an Aethria ink base, using charcoal, verdigris, soft verdigris, and signal-blue notes. This should read as a blurred landscape or long-exposure scan, not light trails or a neon effect.
- **Texture:** Preserve a low-contrast grain overlay to avoid a flat digital surface.

## Asset system

1. Update the light and dark wordmark SVGs to add open brackets around the wordmark.
2. Update all square SVG marks with bracketed `A` compositions appropriate to 32px and 512px canvases.
3. Maintain existing filenames and `viewBox` sizes so all existing links continue working.
4. Update the asset-page previews and labels where needed so the displayed intent matches the files.

## Banner studio

1. Replace blob generation and radial-gradient drawing with deterministic line-streak generation derived from the existing seeded configuration.
2. Keep the existing platform dimensions, palette controls, layout options, canvas preview, and high-resolution PNG export behavior.
3. Add the bracketed wordmark to the wordmark-only layout and preserve the verdigris full stop. Bracket arms and spacing match the gallery loader: 14px arms with the outer edge 26px from the mark.
4. Use palette colors as subtle motion accents while ensuring readable ink typography above the background.

## Verification

- Open `brand-assets/index.html` locally and confirm each logo preview loads, bracket geometry is visible, and downloads retain SVG vector content.
- Exercise every platform and layout in the banner studio, including a PNG export, to confirm no canvas errors and readable text.
- Run the web frontend's existing checks to verify no unrelated marketing code is affected.

## Out of scope

- Changing the marketing site's loader implementation or its fonts/tokens.
- Replacing the existing static hero PNG.
- Adding new runtime dependencies or changing public asset filenames.
