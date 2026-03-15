# Animation philosophy for Aethria

## Goal

Animations should make the app feel **fluid and coherent**, not stiff or decorative. Every motion should either (1) communicate state or context change, or (2) make transitions between views feel continuous rather than abrupt. The product is institutional (dealflow OS) but that does not mean motionless — it means purposeful and smooth.

## Principles

- **Token-only timing:** All durations and easing come from `tokens.motion` (or CSS `var(--motion-*)`) so the whole app shares one rhythm.
- **Prefer short/medium over micro for “content appears”:** Use `short` (0.4s) or `medium` (0.5s) for fades and slides when content or a new view appears. Reserve `micro` (0.15s) for very quick feedback (e.g. toggle state, inline validation).
- **Subtle motion beats opacity-only:** A small `y` (e.g. 6–10px) with opacity makes “something appeared” feel like it settled in rather than popped. Use for: list items, panels, modal content, feed rows.
- **Stagger for lists and feeds:** When multiple items appear together (feed rows, WorkGrid cards), a small per-item delay (e.g. 0.02–0.03s) creates a cascade and makes the list feel alive without feeling slow.
- **No gimmicky reveals:** Avoid effects that draw attention to the effect itself (e.g. character scramble, slot-machine text). Prefer a quick fade or fade+slide so the user focuses on the content.

## Changes made (fluidity pass)

1. **Investment memo – scramble removed**
   - The company name used a scramble/decode effect (random chars resolving to the name). It felt like a terminal or game effect and didn’t match an institutional memo.
   - **Replaced with:** The memo header (label, company name, sector) fades in and moves up slightly (opacity 0, y: 10 → 1, 0) over `short` duration. The title is visible immediately in content terms; only the entrance is animated.

2. **GhostTransition**
   - Was reduced to a very fast micro fade, so list changes felt abrupt.
   - **Restored:** Fade + slight vertical motion: `initial { opacity: 0, y: 6 }`, `animate { opacity: 1, y: 0 }`, `exit { opacity: 0, y: -4 }` with `short` duration. List updates feel like a continuous flow.

3. **LiveIntelligenceFeed**
   - Per-row stagger was removed, so new entries popped in as a block.
   - **Restored:** Each row animates in with a small delay (`i * 0.025`) and `short` duration, plus a slight `y: 6` so the feed feels like a stream of entries appearing one after another.

4. **Tab content (SystemIntelligence, Settings)**
   - Tab panels used `micro` for the content switch.
   - **Updated:** Content transition uses `short` so switching tabs feels like a smooth panel change, not a flash.

5. **Existing fluid pieces kept**
   - WorkGrid: per-row cascade (delay `index * 0.03`) and fade+slide for cards.
   - Login: staggered fade+slide for wordmark, subtitle, form, button, footer.
   - LoadingAnimation: longer orbit (1.2s, custom ease) for calibration feel.
   - SystemBar: first-time entrance with `long` duration.
   - Panel overlay: medium-duration slide and backdrop.

## Summary

- **Removed:** Memo title scramble (replaced with simple fluid title reveal).
- **Restored/strengthened:** GhostTransition (fade + y, short), LiveIntelligenceFeed stagger + short duration, tab content transition (short).
- **Result:** One consistent, token-based motion system with fluid list/panel/tab transitions and no “decoding” or gimmicky text effects.
