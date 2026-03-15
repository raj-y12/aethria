# Pass 5 — Motion and animation audit

## Token system (tokens.motion)

- **ease:** [0.16, 1, 0.3, 1] (Framer)
- **easeCss:** 'cubic-bezier(0.16, 1, 0.3, 1)' (CSS)
- **duration.micro:** 0.15s — tab switch, menu expand, quick feedback
- **duration.short:** 0.4s — content entrance
- **duration.medium:** 0.5s — panels, overlays
- **duration.long:** 0.6s — page-level transitions

## Inventory

| Location | Element | Duration | Easing | Uses tokens? |
|----------|---------|----------|--------|--------------|
| SystemBar | header entrance | 0.8 | ease | No (0.8 hardcoded) |
| SystemBar | toggle buttons | duration-200 | easeCss | Partial (200ms inline) |
| SystemBar | Log out button | duration-200, hover:-translate-y | — | Partial |
| GhostTransition | exit only | medium | ease | Yes (entry = animate, no effect) |
| WorkGrid | row entrance | short, delay index*0.03 | ease | Yes (cascade = decorative) |
| WorkGrid | selected dot | short | ease | Yes |
| WorkGrid | one-liner expand | duration-200 ease-out | — | No |
| WorkGrid | "→ memo" hover | duration-200 | — | No |
| MainLayout | mobile menu | micro | ease | Yes |
| MainLayout | overlay backdrop/panel | medium | ease | Yes |
| MainLayout | empty state text | duration-200 | — | No |
| PanelShell | tab buttons | duration-200 | — | No |
| SettingsPage | mobile menu | micro | ease | Yes |
| SettingsPage | main wrapper | short | ease | Yes |
| SettingsPage | tab content | micro | ease | Yes |
| SettingsPage | input | duration-150 | — | No |
| SettingsPage | Toggle | duration-300, 0.2s transform | easeCss | Partial |
| SettingsPage | Save button | — | — | — |
| LiveIntelligenceFeed | row | short, delay i*0.02 | ease | Yes (decorative stagger) |
| SystemIntelligence | BarFill | short | ease | Yes |
| SystemIntelligence | escalation resolved | micro | ease | Yes |
| SystemIntelligence | tab content | micro | ease | Yes |
| SystemIntelligence | buttons | transition-colors | — | — |
| LoginPage | wordmark, subtitle, form, footer | short/micro, delays 0.3–0.9 | ease | Yes |
| LoginPage | underline | long, delay 0.3 | ease | Yes |
| LoginPage | button | duration-150 | — | No |
| LoginPage | loading dots | 0.6 repeat | — | No |
| LoginPage | CTA dash width | duration-200 ease-out | — | No (remove) |
| LoadingAnimation | orbit points | 1.2, repeatDelay 0.1, delay 0.25+i*0.12 | EASE custom | No |
| InvestmentMemo | modal | medium | ease | Yes |
| InvestmentMemoContent | action buttons | — | — | active:opacity-80 |
| MobileHeader | link, button | transition-opacity/duration-200 | — | No |
| index.css | escalation-pulse | 2s ease-in-out | — | No |
| index.css | escalation-dot-active | 2s ease-in-out | — | No |

## Violations to fix

1. Replace all hardcoded ms (150, 200, 300, 800) and seconds (0.6, 1.2, 2) with token refs or token-derived CSS vars.
2. GhostTransition: entry does nothing; fix or remove.
3. WorkGrid: per-row delay on initial load = decorative; only animate new arrivals.
4. Login CTA: remove dash width animation; simple hover.
5. Buttons: one model (hover, active: translate-y + opacity, focus, disabled).
6. LoadingAnimation: use tokens (e.g. short or medium for cycle; ease from tokens).
7. CSS keyframes: use token easing/duration where applicable (e.g. 2s for pulse can stay for "slow urgency" but ease → cubic-bezier from tokens).

---

## After Pass 5

- **CSS vars:** :root has --motion-ease, --motion-micro/short/medium/long. Escalation keyframes use 2s + var(--motion-ease).
- **btn-interaction:** Single class for transition (token duration/ease), active:translate-y-px + opacity 0.9, disabled:opacity 0.7. Applied to all buttons and interactive links.
- **GhostTransition:** Now has real entry (opacity 0→1) and exit (opacity 0), token micro duration.
- **WorkGrid:** seenIdsRef primes on first non-empty load; only items not in that set animate in (new arrivals). No per-row delay.
- **Login:** CTA is "LOG IN" only; hover:opacity-90, btn-interaction. Loading dots use tokens.motion.duration.short and ease.
- **LoadingAnimation:** duration, ease, repeatDelay, delay from tokens.
- **SystemBar:** entrance uses tokens.motion.duration.long (was 0.8).
- **LiveIntelligenceFeed:** no stagger; transition uses tokens.motion.duration.micro.
- All Framer transitions reference tokens.motion.duration.* and tokens.motion.ease. All CSS transitions use var(--motion-*).
