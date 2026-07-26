# Loader Motion Brand Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Aethria's legacy logo assets and radial-gradient banner backgrounds with the marketing loader's bracketed wordmark and a restrained linear motion-blur system.

**Architecture:** Preserve all existing SVG filenames and canvas controls while changing only their artwork and the single-file canvas renderer. The banner renderer will derive deterministic diagonal line strokes from the existing seeded configuration, so previews, preset cards, profile cards, and PNG exports share a stable visual system without new dependencies.

**Tech Stack:** Standalone SVG, HTML/CSS, browser Canvas 2D API, existing npm checks.

## Global Constraints

- Preserve all files in `brand-assets/assets/` and their current filenames/viewBox dimensions.
- Keep banner platform sizes, controls, layouts, and PNG export resolution unchanged.
- Use Playfair Display for the wordmark and `#3d6b5e` for its full stop.
- Use thin open brackets matching the gallery-loader's 1px visual weight.
- Do not modify the marketing loader implementation or add dependencies.
- Keep output user-scoped/backend files untouched.

---

### Task 1: Replace the SVG logo family with loader-aligned marks

**Files:**
- Modify: `brand-assets/assets/logo-wordmark-light.svg`
- Modify: `brand-assets/assets/logo-wordmark-dark.svg`
- Modify: `brand-assets/assets/logo-monogram-light.svg`
- Modify: `brand-assets/assets/logo-monogram-dark.svg`
- Modify: `brand-assets/assets/logo-icon-light.svg`
- Modify: `brand-assets/assets/logo-icon-transparent.svg`
- Modify: `brand-assets/assets/favicon.svg`

**Interfaces:**
- Consumes: The loader’s bracket proportions in `web-front-end/src/index.css:414-432` and wordmark styling in `web-front-end/src/index.css:433-445`.
- Produces: SVGs retaining their existing names, dimensions, and light/dark/transparent semantics for `brand-assets/index.html` download links.

- [ ] **Step 1: Add the bracketed wordmark artwork**

  In both wordmark SVGs, retain the 480 × 120 canvas and surface rectangle. Position the `Aethria` text centrally, use a separate verdigris `.` text node, and add left/right open bracket paths with `fill="none"`, `stroke` set to the contrast ink, `stroke-width="1"`, and square line caps. Use the light surface `#d9d7d4` and deep ink `#0a1629` to match the marketing loader.

- [ ] **Step 2: Add small-format bracketed marks**

  For the 512px monograms, keep a centred Playfair `A`, use bracket paths at a comfortable inset, and use the light/deep inverse palette. For 32px icon and favicon variants, use a simplified `A` plus narrow open brackets with a stroke that remains visible at favicon size; retain the transparent background only in `logo-icon-transparent.svg`.

- [ ] **Step 3: Validate SVG syntax and dimensions**

  Run:

  ```bash
  for file in brand-assets/assets/*.svg; do xmllint --noout "$file"; done
  rg -n 'viewBox="0 0 (32 32|480 120|512 512)"' brand-assets/assets/*.svg
  ```

  Expected: every SVG parses successfully and retains one of the existing canvas sizes.

- [ ] **Step 4: Commit the logo system**

  ```bash
  git add brand-assets/assets/favicon.svg brand-assets/assets/logo-*.svg
  git commit -m "feat: align logo assets with loader mark"
  ```

### Task 2: Replace radial meshes with deterministic motion-line fields

**Files:**
- Modify: `brand-assets/index.html:627-716`

**Interfaces:**
- Consumes: `cfg.seed`, `cfg.w`, `cfg.h`, `cfg.base`, `cfg.ink`, and `cfg.colors` supplied by the studio and preset gallery.
- Produces: `buildStreaks(cfg, w, h)` and `drawStreakField(ctx, cfg, scale)` that draw a consistent diagonal motion background for any canvas dimensions.

- [ ] **Step 1: Remove radial blob helpers**

  Replace `buildBlobs`, `radial`, and `drawBlob` with a seeded streak generator. Each streak object must contain `x`, `y`, `length`, `width`, `alpha`, `color`, and an angle concentrated around a single diagonal direction. Generate a mixture of long, low-opacity lines and fewer short, brighter accent lines; choose colors cyclically from `cfg.colors`.

- [ ] **Step 2: Render the motion field**

  Implement `drawStreakField(ctx, cfg, scale)` to draw all generated lines after the canvas base fill. Use `ctx.lineCap = 'square'`, scale the coordinates and widths, set `globalAlpha` per streak, and restore the context after rendering. Add one soft dark linear wash before grain so banner text remains readable without reintroducing radial gradients.

- [ ] **Step 3: Wire the renderer into all canvas outputs**

  Rename `renderMesh` to `renderBanner` and call `drawStreakField` instead of blob rendering. Update the studio preview, full-resolution download, preset gallery previews/downloads, and profile rendering to use the renamed renderer or the shared streak helper. Preserve the current `applyGrain` and text-on-top order.

- [ ] **Step 4: Run the static radial-mesh regression check**

  Run:

  ```bash
  rg -n 'buildBlobs|drawBlob|createRadialGradient|renderMesh' brand-assets/index.html
  ```

  Expected: no matches, proving the banner source no longer uses the circular-gradient mesh primitives.

- [ ] **Step 5: Commit the motion renderer**

  ```bash
  git add brand-assets/index.html
  git commit -m "feat: render brand banners as motion streaks"
  ```

### Task 3: Bring all on-page brand compositions into the bracketed system

**Files:**
- Modify: `brand-assets/index.html:395-405`
- Modify: `brand-assets/index.html:518-543`
- Modify: `brand-assets/index.html:766-784`
- Modify: `brand-assets/index.html:923-977`

**Interfaces:**
- Consumes: The bracket geometry and mark palette introduced in Task 1, and the line-field helpers from Task 2.
- Produces: Accurate page copy, previews, wordmark-only banners, and profile images that visibly use the same bracketed identity.

- [ ] **Step 1: Update brand-studio language and asset metadata**

  Change the masthead description from “gradient-mesh studio” to a concise description of the motion-line studio. Update wordmark/monogram/icon labels and alt text to mention the bracketed mark where appropriate, without changing link paths or download names.

- [ ] **Step 2: Draw brackets around canvas wordmarks**

  Add a `drawBrackets(ctx, x, top, width, height, scale, color)` helper. Call it from `wordmarkCenter` after measuring the wordmark width, using the same 1px visual line weight and offset as the SVG. Call the helper for both plain and coloured profile wordmark modes; for profile monograms, call it around the central `A`.

- [ ] **Step 3: Keep text readable across all banner layouts**

  Keep `drawText` as the final drawing stage. Confirm its `wordmark` layout shows the bracketed wordmark, with `cfg.colors[0]` only on the full stop, and that statement, centre, and tagline layouts retain their current content positioning.

- [ ] **Step 4: Commit presentation integration**

  ```bash
  git add brand-assets/index.html
  git commit -m "feat: apply bracketed brand system in studio"
  ```

### Task 4: Verify brand assets in browser and repository checks

**Files:**
- Verify: `brand-assets/index.html`
- Verify: `brand-assets/assets/*.svg`
- Verify: `web-front-end/`

**Interfaces:**
- Consumes: Completed SVG family and browser canvas renderer.
- Produces: Evidence that previews/download paths work, all layouts render, and unaffected marketing checks still pass.

- [ ] **Step 1: Serve and inspect the asset page**

  Run:

  ```bash
  python3 -m http.server 4173 --directory brand-assets
  ```

  Open `http://localhost:4173`, confirm all seven SVG previews load, then exercise each platform, all four layouts, one preset card download, and the studio PNG download. Confirm the field is streak-based, the brackets frame the wordmark, and text remains legible.

- [ ] **Step 2: Run the existing marketing checks**

  Run:

  ```bash
  npm run check:marketing
  npm run build
  ```

  Working directory: `web-front-end`

  Expected: both commands exit with status 0.

- [ ] **Step 3: Inspect the final change set**

  Run:

  ```bash
  git diff HEAD~3..HEAD --check
  git status --short
  ```

  Expected: no whitespace errors and no uncommitted implementation files.

- [ ] **Step 4: Commit verification notes only if a documentation update is needed**

  Do not create a documentation-only commit when verification requires no source changes.
