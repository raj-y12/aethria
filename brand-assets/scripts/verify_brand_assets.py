#!/usr/bin/env python3
"""Check the generated brand assets against their published constraints.

Run after ``generate_brand_assets.py``. The checks encode the requirements the
assets have to satisfy in the wild, so a regression in the generator surfaces
here rather than in the Google Admin console upload dialog.

Sources for the Workspace limits are cited in brand-assets/README.md.

Usage::

    python3 brand-assets/scripts/verify_brand_assets.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ASSETS = pathlib.Path(__file__).resolve().parents[1] / "assets"
WORKSPACE = ASSETS / "google-workspace"

# The palette the marketing site actually renders (web-front-end/src/index.css).
PALETTE = {
    (217, 215, 212): "--stock",
    (10, 22, 41): "--ink",
    (61, 107, 94): "--accent",
    (122, 171, 154): "--color-brand-mark-inverse",
}

EXPECTED_PNG = {
    "workspace-admin-logo-320x132-light.png": (320, 132),
    "workspace-admin-logo-320x132-dark.png": (320, 132),
    "workspace-app-logo-120x120.png": (120, 120),
    "workspace-app-logo-256x256.png": (256, 256),
    "workspace-app-logo-512x512.png": (512, 512),
    "workspace-app-logo-1024x1024.png": (1024, 1024),
    "marketplace-icon-32x32.png": (32, 32),
    "marketplace-icon-48x48.png": (48, 48),
    "marketplace-icon-96x96.png": (96, 96),
    "marketplace-icon-128x128.png": (128, 128),
    "marketplace-tile-220x140.png": (220, 140),
    "marketplace-tile-440x280.png": (440, 280),
    "marketplace-marquee-1400x560.png": (1400, 560),
    "workspace-avatar-256x256.png": (256, 256),
}

# Google Admin console rejects a company logo above 30 KB.
ADMIN_LOGO_MAX_KB = 30
ADMIN_LOGOS = (
    "workspace-admin-logo-320x132-light.png",
    "workspace-admin-logo-320x132-dark.png",
)

# Transparent lockups must keep their alpha; solid tiles must not have any.
ALPHA_EXPECTATIONS = {
    "lockup-2048-transparent.png": True,
    "lockup-2048-inverse-transparent.png": True,
    "workspace-app-logo-512x512.png": False,
    "marketplace-marquee-1400x560.png": False,
}


def main() -> int:
    from PIL import Image

    failures: list[str] = []

    svgs = sorted(ASSETS.glob("*.svg"))
    if not svgs:
        sys.exit("No SVGs found — run generate_brand_assets.py first.")

    # Outlined paths only: an asset that still references a font renders as a
    # fallback serif on any machine without Playfair Display installed.
    for path in svgs:
        source = path.read_text(encoding="utf-8")
        if "<text" in source or "font-family" in source:
            failures.append(f"{path.name}: depends on an installed font")
        for value in set(re.findall(r"#[0-9a-fA-F]{6}", source)):
            rgb = tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))
            if rgb not in PALETTE:
                failures.append(f"{path.name}: off-palette colour {value}")
    print(f"  {len(svgs)} SVGs: outlined, on-palette")

    for name, expected in EXPECTED_PNG.items():
        path = WORKSPACE / name
        if not path.is_file():
            failures.append(f"{name}: missing")
            continue
        size = Image.open(path).size
        if size != expected:
            failures.append(f"{name}: {size[0]}x{size[1]}, expected {expected[0]}x{expected[1]}")
    print(f"  {len(EXPECTED_PNG)} PNGs: exact dimensions")

    for name in ADMIN_LOGOS:
        kb = (WORKSPACE / name).stat().st_size / 1024
        if kb > ADMIN_LOGO_MAX_KB:
            failures.append(f"{name}: {kb:.1f} KB over the {ADMIN_LOGO_MAX_KB} KB admin limit")
    print(f"  admin logos within {ADMIN_LOGO_MAX_KB} KB")

    for name, should_have_alpha in ALPHA_EXPECTATIONS.items():
        image = Image.open(WORKSPACE / name)
        has_alpha = image.mode == "RGBA" and image.getextrema()[3][0] < 255
        if has_alpha is not should_have_alpha:
            failures.append(f"{name}: alpha={has_alpha}, expected {should_have_alpha}")
    print("  alpha channels as specified")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nAll brand-asset checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
