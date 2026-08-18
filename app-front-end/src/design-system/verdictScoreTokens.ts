/**
 * Named hex constants for verdict/score-band color, shared by the decision
 * threshold slider and fund configuration defaults so neither carries a bare
 * hex literal (AGENTS.md: "named design tokens only, no raw hex").
 */

/** Score-band dot colors — deep enough to read as dots on the #D9D7D4 paper; pastels disappear at this dot size. */
export const SCORE_BAND_DOT_COLORS = {
  pass: '#b4635b',
  monitor: '#a8862b',
  invest: '#4a8a6c',
} as const;

/** Verdict badge fill colors — cooled, muted family shared across decision and reviewer-quality badges. */
export const VERDICT_BADGE_FILL_COLORS = {
  invest: '#c3d3c9',
  monitor: '#cfccbb',
  pass: '#d6c4c0',
} as const;

/** Badge text ink/paper pair, picked by contrast against a given fill — distinct from body-text oxford/paper. */
export const BADGE_TEXT_CONTRAST_COLORS = {
  ink: '#1a2b48',
  paper: '#fffdf7',
} as const;
