/**
 * Clerk component appearance — matches Aethria design tokens.
 * Palette: deep blue #001433, paper #F4F1EA, inverse paper.
 * Typography: Geist Sans (body), Space Mono (labels/actions); no rounded corners.
 */
import { tokens } from './tokens';

const OXFORD = tokens.color.oxford;
const PAPER = tokens.color.paper;
const IVORY = tokens.color.ivory;
const OXFORD_RGB = '0, 20, 51';
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

/** UserProfile (Account tab) — match Aethria: oxford, paper, Geist Sans / Space Mono, no radius */
export const userProfileAppearance = {
  variables: {
    ...clerkAppearance.variables,
    colorModalBackdrop: oxfordAlpha(0.4),
    fontFamily: tokens.font.body,
    fontFamilyButtons: tokens.font.mono,
    borderRadius: '0',
    colorText: OXFORD,
    colorTextSecondary: oxfordAlpha(0.6),
  },
  elements: {
    rootBox: {
      backgroundColor: PAPER,
      fontFamily: tokens.font.body,
      color: OXFORD,
    },
    card: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
      boxShadow: 'none',
    },
    navbar: {
      backgroundColor: oxfordAlpha(0.04),
      borderRight: tokens.frameBorder,
    },
    navbarButton: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.6),
    },
    navbarButtonIcon: {
      color: oxfordAlpha(0.4),
    },
    pageScrollBox: {
      backgroundColor: PAPER,
    },
    profileSectionTitle: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelSection.size,
      letterSpacing: tokens.type.labelSection.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.6),
    },
    profileSectionTitleText: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelSection.size,
      letterSpacing: tokens.type.labelSection.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.6),
    },
    formFieldLabel: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.6),
    },
    formFieldInput: {
      fontFamily: tokens.font.body,
      fontSize: tokens.type.bodySm.size,
      color: OXFORD,
      backgroundColor: 'transparent',
      border: 'none',
      borderBottom: `1px solid ${oxfordAlpha(0.25)}`,
      borderRadius: 0,
    },
    formButtonPrimary: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      backgroundColor: OXFORD,
      color: IVORY,
      borderRadius: 0,
    },
    formResendCodeLink: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      color: oxfordAlpha(0.6),
    },
    badge: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.meta.size,
      letterSpacing: tokens.type.meta.letterSpacing,
      borderRadius: 0,
    },
    modalContent: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
      boxShadow: 'none',
    },
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
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: oxfordAlpha(0.8),
    },
    userButtonPopoverActionButtonIcon: {
      color: oxfordAlpha(0.4),
    },
  },
};
