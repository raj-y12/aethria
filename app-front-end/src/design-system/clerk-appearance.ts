/**
 * Clerk component appearance — matches Aethria design tokens.
 * Palette: deep blue #0a1629, paper #D9D7D4, inverse paper.
 * Typography: Geist Sans (body), Space Mono (labels/actions); no rounded corners.
 */
import { tokens } from './tokens';

const OXFORD = tokens.color.oxford;
const PAPER = tokens.color.paper;
const IVORY = tokens.color.ivory;
const OXFORD_RGB = '10, 22, 41';
const oxfordAlpha = (alpha: number): string => `rgba(${OXFORD_RGB}, ${alpha})`;
const BORDER = oxfordAlpha(0.06);

export const clerkAppearance = {
  variables: {
    colorPrimary: OXFORD,
    colorBackground: PAPER,
    colorForeground: OXFORD,
    colorPrimaryForeground: IVORY,
    colorMutedForeground: oxfordAlpha(0.6),
    colorMuted: oxfordAlpha(0.06),
    colorBorder: BORDER,
    colorInput: PAPER,
    colorInputForeground: OXFORD,
    colorRing: OXFORD,
    colorNeutral: OXFORD,
    colorShadow: 'transparent',
    fontFamily: tokens.font.body,
    fontFamilyButtons: tokens.font.mono,
    borderRadius: '0',
  },
};

/** UserButton-specific appearance (avatar + popover) — matches system bar and app chrome */
export const userButtonAppearance = {
  variables: {
    ...clerkAppearance.variables,
  },
  elements: {
    userButtonAvatarBox: {
      width: 40,
      height: 40,
      border: `1px solid ${BORDER}`,
      boxShadow: 'none',
    },
    userButtonTrigger: {
      '&:hover': {
        opacity: 0.9,
      },
    },
    userButtonPopoverCard: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
      boxShadow: 'none',
    },
    userButtonPopoverMain: {
      fontFamily: tokens.font.body,
      fontSize: tokens.type.bodySm.size,
      letterSpacing: '0',
      color: OXFORD,
    },
    userButtonPopoverActionButton: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.action.size,
      fontWeight: tokens.type.action.fontWeight,
      lineHeight: tokens.type.action.lineHeight,
      letterSpacing: tokens.type.action.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.72),
    },
    userButtonPopoverActionButtonIcon: {
      color: oxfordAlpha(0.4),
    },
  },
};
