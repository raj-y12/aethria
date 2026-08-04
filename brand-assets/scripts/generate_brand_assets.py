#!/usr/bin/env python3
"""Generate the Aethria brand asset pack from the live marketing-site logo.

The on-screen logo is the arrival overlay in ``web-front-end`` — a Playfair
Display 500 wordmark inside a pair of hairline brackets
(``GalleryLoader.tsx`` + the "GALLERY LOADER" block of ``index.css``). This
script reproduces that lockup as distributable vector and raster assets.

Two properties make the output usable as a brand asset rather than a
screenshot:

* **Glyphs are outlined to paths.** Nothing depends on Playfair Display being
  installed on the viewer's machine, so an SVG opened in Figma, Illustrator,
  Google Slides or a browser is byte-for-byte the same shape.
* **Text is shaped with HarfBuzz** against the exact ``@fontsource`` file the
  site ships, so kerning matches the browser. ``verify_against_browser()``
  asserts the shaped advance equals the width Chromium reports.

Geometry is derived from the CSS at a reference ``font-size`` of 64px, where
Chromium measures the wordmark box at 231.046875 x 96 (line-height 1.5 via
Tailwind preflight). Everything else is expressed as a ratio of the font size,
so the lockup scales without drift.

Usage::

    python3 brand-assets/scripts/generate_brand_assets.py
    python3 brand-assets/scripts/generate_brand_assets.py --font path/to.woff2

Requires: fonttools[woff2], uharfbuzz, cairosvg, pillow.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = REPO_ROOT / "brand-assets" / "assets"

# ── Palette ────────────────────────────────────────────────────────────────
# Sourced from web-front-end/src/index.css :root. The pre-existing assets had
# drifted onto three different navies (#001433, #1A2B48, #1D2D48); these are
# the tokens the site actually renders.
STOCK = "#d9d7d4"  # --stock       paper / architectural grey
INK = "#0a1629"  # --ink         oxford blue
ACCENT = "#3d6b5e"  # --accent      verdigris, on light
ACCENT_INV = "#7aab9a"  # --color-brand-mark-inverse, on dark
RULE_OPACITY = 0.26  # --line-2 alpha, the bracket hairline

# ── Geometry, as ratios of font-size (measured at font-size 64px) ──────────
REF_FONT_PX = 64.0
REF_MARK_W = 231.046875  # Chromium-measured advance of "Aethria."
LINE_HEIGHT = 1.5  # Tailwind v3 preflight html { line-height: 1.5 }
BRACKET_W = 14.0 / REF_FONT_PX  # .gallery-loader-mark::before width
BRACKET_OVERHANG = 14.0 / REF_FONT_PX  # top:-14px / bottom:-14px
BRACKET_GAP = 12.0 / REF_FONT_PX  # left:-26px minus the 14px width
BRACKET_STROKE = 1.0 / REF_FONT_PX  # border: 1px solid


@dataclass(frozen=True)
class Theme:
    """A background/foreground pairing for one asset variant."""

    name: str
    background: str | None
    ink: str
    accent: str

    @property
    def rule(self) -> str:
        return self.ink


LIGHT = Theme("light", STOCK, INK, ACCENT)
DARK = Theme("dark", INK, STOCK, ACCENT_INV)
TRANSPARENT = Theme("transparent", None, INK, ACCENT)
TRANSPARENT_INV = Theme("inverse-transparent", None, STOCK, ACCENT_INV)


# ── Font loading and shaping ───────────────────────────────────────────────


def resolve_font(explicit: str | None) -> Path:
    """Locate the Playfair Display 500 file the marketing site ships.

    Prefers the installed @fontsource package so the assets and the website can
    never disagree about which cut of the typeface is canonical.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            sys.exit(f"--font not found: {path}")
        return path

    candidates = [
        REPO_ROOT
        / "web-front-end/node_modules/@fontsource/playfair-display/files"
        / "playfair-display-latin-500-normal.woff2",
        REPO_ROOT
        / "app-front-end/node_modules/@fontsource/playfair-display/files"
        / "playfair-display-latin-500-normal.woff2",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    sys.exit(
        "Playfair Display 500 not found. Run `npm ci` in web-front-end, or pass\n"
        "  --font <path to playfair-display-latin-500-normal.woff2>"
    )


class Typesetter:
    """Shapes a string and emits outlined SVG path data for each glyph."""

    def __init__(self, font_path: Path) -> None:
        from fontTools.ttLib import TTFont

        self._tmpdir = Path(tempfile.mkdtemp(prefix="aethria-brand-"))
        ttf_path = self._tmpdir / "playfair-500.ttf"

        # HarfBuzz cannot read woff2; fontTools decompresses on load, so round
        # -trip through a plain TTF before shaping.
        font = TTFont(str(font_path))
        font.flavor = None
        font.save(str(ttf_path))

        self.font = TTFont(str(ttf_path))
        self.upem = self.font["head"].unitsPerEm
        self.ascender = self.font["hhea"].ascender
        self.descender = self.font["hhea"].descender
        self.cap_height = self.font["OS/2"].sCapHeight
        self.glyph_set = self.font.getGlyphSet()
        self.glyph_order = self.font.getGlyphOrder()

        import uharfbuzz as hb

        self._hb = hb
        blob = hb.Blob.from_file_path(str(ttf_path))
        face = hb.Face(blob)
        self._hb_font = hb.Font(face)
        self._hb_font.scale = (self.upem, self.upem)

    def cleanup(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def shape(self, text: str) -> tuple[list[dict], float]:
        """Return positioned glyphs (in font units) and the total advance."""
        buf = self._hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        self._hb.shape(self._hb_font, buf, {"kern": True, "liga": True})

        glyphs: list[dict] = []
        pen_x = 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyphs.append(
                {
                    "name": self.glyph_order[info.codepoint],
                    "cluster": info.cluster,
                    "x": pen_x + pos.x_offset,
                    "y": pos.y_offset,
                }
            )
            pen_x += pos.x_advance
        return glyphs, pen_x

    def outline(self, glyph_name: str, scale: float, x: float, baseline: float) -> str:
        """Draw one glyph as SVG path data, flipped into SVG's y-down space."""
        from fontTools.misc.transform import Transform
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen

        # Three decimals is well below a device pixel at any size these assets
        # ship at, and keeps the committed SVGs readable and diffable.
        pen = SVGPathPen(self.glyph_set, ntos=_fmt)
        transform = TransformPen(pen, Transform(scale, 0, 0, -scale, x, baseline))
        self.glyph_set[glyph_name].draw(transform)
        return pen.getCommands()

    def ink_bounds(
        self, glyphs: list[dict], scale: float, x: float, baseline: float
    ) -> tuple[float, float, float, float]:
        """Union bounding box of drawn ink — used for optical centring.

        Centring on the advance width leaves a mark visibly off-centre, because
        the trailing period carries a right side bearing the eye does not see.
        """
        from fontTools.misc.transform import Transform
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.pens.transformPen import TransformPen

        pen = BoundsPen(self.glyph_set)
        for glyph in glyphs:
            transform = TransformPen(
                pen,
                Transform(scale, 0, 0, -scale, x + glyph["x"] * scale, baseline - glyph["y"] * scale),
            )
            self.glyph_set[glyph["name"]].draw(transform)
        return pen.bounds


# ── SVG composition ────────────────────────────────────────────────────────


def _fmt(value: float) -> str:
    """Trim float noise so the committed SVGs diff cleanly."""
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def bracket_path(x: float, y: float, width: float, height: float, stroke: float, *, left: bool) -> str:
    """A three-sided CSS border rendered as one filled polygon.

    ``box-sizing: border-box`` (Tailwind preflight) means the 14px width in the
    stylesheet includes the 1px borders, so the outer box is drawn at full size
    and the inner notch subtracted.
    """
    if left:
        pts = [
            (x + width, y),
            (x, y),
            (x, y + height),
            (x + width, y + height),
            (x + width, y + height - stroke),
            (x + stroke, y + height - stroke),
            (x + stroke, y + stroke),
            (x + width, y + stroke),
        ]
    else:
        pts = [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
            (x, y + height - stroke),
            (x + width - stroke, y + height - stroke),
            (x + width - stroke, y + stroke),
            (x, y + stroke),
        ]
    body = " ".join(f"{_fmt(px)} {_fmt(py)}" for px, py in pts)
    return f"M {body} Z"


def build_lockup(
    ts: Typesetter,
    theme: Theme,
    *,
    font_px: float = REF_FONT_PX,
    brackets: bool = True,
    pad: float | None = None,
) -> tuple[str, float, float]:
    """Compose the ``[ Aethria. ]`` lockup. Returns (svg, width, height)."""
    scale = font_px / ts.upem
    glyphs, advance = ts.shape("Aethria.")
    mark_w = advance * scale
    mark_h = LINE_HEIGHT * font_px

    br_w = BRACKET_W * font_px
    br_gap = BRACKET_GAP * font_px
    br_over = BRACKET_OVERHANG * font_px
    br_stroke = BRACKET_STROKE * font_px

    if pad is None:
        # Clear space: half a cap height, the conventional minimum.
        pad = ts.cap_height / ts.upem * font_px * 0.5

    side = (br_w + br_gap) if brackets else 0.0
    content_w = mark_w + 2 * side
    content_h = mark_h + (2 * br_over if brackets else 0.0)
    width = content_w + 2 * pad
    height = content_h + 2 * pad

    mark_x = pad + side
    mark_y = pad + (br_over if brackets else 0.0)

    # CSS half-leading: the line box is taller than the font's content area, so
    # the baseline sits below the box top by half the difference plus ascent.
    content_area = (ts.ascender - ts.descender) / ts.upem * font_px
    baseline = mark_y + (mark_h - content_area) / 2 + ts.ascender / ts.upem * font_px

    parts: list[str] = []
    if theme.background:
        parts.append(f'<rect width="{_fmt(width)}" height="{_fmt(height)}" fill="{theme.background}"/>')

    if brackets:
        left_x = mark_x - br_gap - br_w
        right_x = mark_x + mark_w + br_gap
        rules = "".join(
            bracket_path(bx, pad, br_w, content_h, br_stroke, left=is_left)
            for bx, is_left in ((left_x, True), (right_x, False))
        )
        parts.append(f'<path d="{rules}" fill="{theme.rule}" fill-opacity="{RULE_OPACITY}"/>')

    # "Aethria" is ink; the trailing period is the verdigris accent. Split by
    # HarfBuzz cluster so the colouring survives any ligature substitution.
    dot_cluster = len("Aethria")
    for colour, keep in ((theme.ink, False), (theme.accent, True)):
        d = "".join(
            ts.outline(g["name"], scale, mark_x + g["x"] * scale, baseline - g["y"] * scale)
            for g in glyphs
            if (g["cluster"] >= dot_cluster) == keep
        )
        if d:
            parts.append(f'<path d="{d}" fill="{colour}"/>')

    svg = _svg_document(width, height, parts, title=f"Aethria logo ({theme.name})")
    return svg, width, height


def build_monogram(
    ts: Typesetter,
    theme: Theme,
    *,
    size: float = 512.0,
    brackets: bool = False,
) -> tuple[str, float, float]:
    """Square ``A.`` mark for avatars, favicons and app icons."""
    glyphs, _advance = ts.shape("A.")

    # Size the glyph off cap height so the mark holds a consistent optical
    # weight regardless of canvas, then centre the ink it actually paints.
    # Playfair is a high-contrast serif, so its hairlines are the first thing to
    # go at 32px. Filling ~2/3 of the tile keeps them present without crowding
    # the mark at 1024px. The framed variant sits smaller to leave bracket room.
    cap_fraction = 0.46 if brackets else 0.56
    scale = (size * cap_fraction) / ts.cap_height

    x_min, y_min, x_max, y_max = ts.ink_bounds(glyphs, scale, 0.0, 0.0)
    run_w, run_h = x_max - x_min, y_max - y_min
    origin_x = (size - run_w) / 2 - x_min
    baseline = (size - run_h) / 2 - y_min

    parts: list[str] = []
    if theme.background:
        parts.append(f'<rect width="{_fmt(size)}" height="{_fmt(size)}" fill="{theme.background}"/>')

    if brackets:
        font_px = scale * ts.upem
        br_w = BRACKET_W * font_px
        br_gap = BRACKET_GAP * font_px
        br_stroke = BRACKET_STROKE * font_px
        # Frame the painted ink, matching the lockup's overhang-and-gap ratios.
        ink_x, ink_y = (size - run_w) / 2, (size - run_h) / 2
        box_h = run_h + 2 * BRACKET_OVERHANG * font_px
        box_y = ink_y - BRACKET_OVERHANG * font_px
        rules = "".join(
            bracket_path(bx, box_y, br_w, box_h, br_stroke, left=is_left)
            for bx, is_left in (
                (ink_x - br_gap - br_w, True),
                (ink_x + run_w + br_gap, False),
            )
        )
        parts.append(f'<path d="{rules}" fill="{theme.rule}" fill-opacity="{RULE_OPACITY}"/>')

    for colour, keep in ((theme.ink, False), (theme.accent, True)):
        d = "".join(
            ts.outline(g["name"], scale, origin_x + g["x"] * scale, baseline - g["y"] * scale)
            for g in glyphs
            if (g["cluster"] >= 1) == keep
        )
        if d:
            parts.append(f'<path d="{d}" fill="{colour}"/>')

    svg = _svg_document(size, size, parts, title=f"Aethria monogram ({theme.name})")
    return svg, size, size


def _svg_document(width: float, height: float, parts: list[str], *, title: str) -> str:
    body = "\n  ".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(width)} {_fmt(height)}"'
        f' width="{_fmt(width)}" height="{_fmt(height)}" role="img" aria-label="{title}">\n'
        f"  <title>{title}</title>\n"
        f"  {body}\n"
        f"</svg>\n"
    )


# ── Raster output ──────────────────────────────────────────────────────────


def render_png(
    svg: str,
    out_path: Path,
    width: int,
    height: int,
    *,
    background: str | None,
    supersample: int = 4,
) -> None:
    """Rasterise an SVG, supersampling then Lanczos-downsampling for quality.

    cairo antialiases well on its own, but the bracket hairline is sub-pixel at
    icon sizes; oversampling keeps it from dropping out entirely.
    """
    import cairosvg
    from PIL import Image

    raw = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=width * supersample,
        output_height=height * supersample,
    )
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img = img.resize((width, height), Image.LANCZOS)

    if background:
        flat = Image.new("RGBA", img.size, background)
        flat.alpha_composite(img)
        img = flat.convert("RGB")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def fit_into(
    ts: Typesetter,
    theme: Theme,
    box_w: int,
    box_h: int,
    *,
    margin: float = 0.12,
    brackets: bool = True,
) -> str:
    """Letterbox the lockup into an exact pixel box with even breathing room."""
    probe, nat_w, nat_h = build_lockup(ts, theme, brackets=brackets, pad=0)
    usable_w = box_w * (1 - 2 * margin)
    usable_h = box_h * (1 - 2 * margin)
    scale = min(usable_w / nat_w, usable_h / nat_h)
    draw_w, draw_h = nat_w * scale, nat_h * scale
    x, y = (box_w - draw_w) / 2, (box_h - draw_h) / 2

    # The box paints its own background, so the scaled lockup contributes
    # drawing content only.
    body = [f'<rect width="{box_w}" height="{box_h}" fill="{theme.background}"/>'] if theme.background else []
    body.append(
        f'<g transform="translate({_fmt(x)} {_fmt(y)}) scale({scale:.6f})">'
        f"{_strip_background(probe, theme)}</g>"
    )
    return _svg_document(box_w, box_h, body, title="Aethria logo")


def _strip_background(svg: str, theme: Theme) -> str:
    """Return an SVG's drawing content minus its wrapper and background rect."""
    inner = svg.split("</title>", 1)[1].rsplit("</svg>", 1)[0].strip()
    if theme.background and inner.startswith("<rect"):
        inner = inner.split("/>", 1)[1].strip()
    return inner


# ── Verification ───────────────────────────────────────────────────────────


def verify_against_browser(ts: Typesetter) -> None:
    """Assert our shaping matches what Chromium measured for the live logo."""
    _, advance = ts.shape("Aethria.")
    measured = advance * (REF_FONT_PX / ts.upem)
    if abs(measured - REF_MARK_W) > 0.01:
        sys.exit(
            f"Shaped advance {measured:.4f}px does not match the browser-measured "
            f"{REF_MARK_W}px. The font file or shaping settings changed."
        )
    print(f"  shaping matches browser: {measured:.6f}px == {REF_MARK_W}px")


# ── Asset manifest ─────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", help="Path to playfair-display-latin-500-normal.woff2")
    parser.add_argument("--out", default=str(ASSETS_DIR), help="Output directory")
    args = parser.parse_args()

    out = Path(args.out)
    ts = Typesetter(resolve_font(args.font))
    try:
        print("Verifying shaping…")
        verify_against_browser(ts)

        manifest: list[dict] = []

        def write_svg(name: str, svg: str, w: float, h: float, note: str) -> None:
            path = out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")
            manifest.append({"file": name, "w": round(w, 2), "h": round(h, 2), "use": note})
            print(f"  {name:<46} {round(w)}x{round(h)}")

        print("\nVector masters — bracketed lockup (primary logo):")
        for theme in (LIGHT, DARK, TRANSPARENT, TRANSPARENT_INV):
            svg, w, h = build_lockup(ts, theme)
            write_svg(f"logo-lockup-{theme.name}.svg", svg, w, h, "Primary logo")

        print("\nVector masters — wordmark (no brackets, tight spaces):")
        for theme in (LIGHT, DARK, TRANSPARENT, TRANSPARENT_INV):
            svg, w, h = build_lockup(ts, theme, brackets=False)
            write_svg(f"logo-wordmark-{theme.name}.svg", svg, w, h, "Wordmark")

        print("\nVector masters — monogram (square):")
        for theme in (LIGHT, DARK, TRANSPARENT, TRANSPARENT_INV):
            svg, w, h = build_monogram(ts, theme)
            write_svg(f"logo-monogram-{theme.name}.svg", svg, w, h, "Square mark")

        print("\nVector masters — framed monogram (256px and above):")
        for theme in (LIGHT, DARK):
            svg, w, h = build_monogram(ts, theme, brackets=True)
            write_svg(f"logo-monogram-framed-{theme.name}.svg", svg, w, h, "Square mark, framed")

        # Back-compat filenames referenced by brand-assets/index.html.
        icon_light, w, h = build_monogram(ts, DARK, size=32)
        write_svg("logo-icon-light.svg", icon_light, w, h, "App icon")
        icon_transparent, w, h = build_monogram(ts, TRANSPARENT, size=32)
        write_svg("logo-icon-transparent.svg", icon_transparent, w, h, "App icon, transparent")
        favicon, w, h = build_monogram(ts, DARK, size=32)
        write_svg("favicon.svg", favicon, w, h, "Favicon")

        print("\nGoogle Workspace raster pack:")
        gw = out / "google-workspace"
        if gw.exists():
            shutil.rmtree(gw)

        rendered: list[dict] = []

        def emit(name: str, svg: str, w: int, h: int, bg: str | None, note: str) -> None:
            path = gw / name
            render_png(svg, path, w, h, background=bg)
            kb = path.stat().st_size / 1024
            rendered.append({"file": f"google-workspace/{name}", "w": w, "h": h, "kb": round(kb, 1), "use": note})
            print(f"  {name:<46} {w}x{h}  {kb:6.1f} KB   {note}")

        # Admin console company logo — displayed at exactly 320x132, max 30 KB.
        for theme in (LIGHT, DARK):
            emit(
                f"workspace-admin-logo-320x132-{theme.name}.png",
                fit_into(ts, theme, 320, 132),
                320,
                132,
                theme.background,
                "Admin console company logo",
            )

        # OAuth consent screen / app identity — square, 120px minimum.
        for size in (120, 256, 512, 1024):
            svg, _, _ = build_monogram(ts, DARK, size=size)
            emit(
                f"workspace-app-logo-{size}x{size}.png",
                svg,
                size,
                size,
                DARK.background,
                "OAuth consent screen / app identity" if size == 120 else "App identity, hi-res",
            )

        # Marketplace store listing icons.
        for size in (32, 48, 96, 128):
            svg, _, _ = build_monogram(ts, DARK, size=size)
            emit(
                f"marketplace-icon-{size}x{size}.png",
                svg,
                size,
                size,
                DARK.background,
                "Marketplace application icon",
            )

        # Marketplace promotional artwork.
        for name, w, h, note in (
            ("marketplace-tile-220x140", 220, 140, "Marketplace card banner"),
            ("marketplace-tile-440x280", 440, 280, "Marketplace large tile"),
            ("marketplace-marquee-1400x560", 1400, 560, "Marketplace marquee"),
        ):
            emit(f"{name}.png", fit_into(ts, DARK, w, h, margin=0.16), w, h, DARK.background, note)

        # Chat app avatar / Google profile picture.
        svg, _, _ = build_monogram(ts, DARK, size=256)
        emit("workspace-avatar-256x256.png", svg, 256, 256, DARK.background, "Chat app / profile avatar")

        # Transparent-background lockups for slide decks and documents.
        for theme in (TRANSPARENT, TRANSPARENT_INV):
            svg, w, h = build_lockup(ts, theme)
            scale = 2048 / w
            emit(
                f"lockup-2048-{theme.name}.png",
                svg,
                2048,
                round(h * scale),
                None,
                "Transparent lockup for Docs/Slides",
            )

        (out / "MANIFEST.json").write_text(
            json.dumps({"vector": manifest, "raster": rendered}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {len(manifest)} vector + {len(rendered)} raster assets to {out}")
    finally:
        ts.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
