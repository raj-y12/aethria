/**
 * Clerk component appearance — matches Aethria design tokens.
 * Palette: oxford #002147, paper #F2F0EA, inverse #FFFFFF.
 * Typography: Geist Sans (body), Space Mono (labels/actions); no rounded corners.
 */
import { tokens } from './tokens';

const OXford = tokens.color.oxford;
const PAPER = tokens.color.paper;
const IVORY = tokens.color.ivory;
const BORDER = 'rgba(0, 33, 71, 0.06)';

export const clerkAppearance = {
  variables: {
    colorPrimary: OXford,
    colorBackground: PAPER,
    colorForeground: OXford,
    colorPrimaryForeground: IVORY,
    colorMutedForeground: 'rgba(0, 33, 71, 0.6)',
    colorMuted: 'rgba(0, 33, 71, 0.06)',
    colorBorder: BORDER,
    colorInput: PAPER,
    colorInputForeground: OXford,
    colorRing: OXford,
    colorNeutral: OXford,
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
    colorModalBackdrop: 'rgba(0, 33, 71, 0.4)',
    fontFamily: tokens.font.body,
    fontFamilyButtons: tokens.font.mono,
    borderRadius: '0',
    colorText: OXford,
    colorTextSecondary: 'rgba(0, 33, 71, 0.6)',
  },
  elements: {
    rootBox: {
      backgroundColor: PAPER,
      fontFamily: tokens.font.body,
      color: OXford,
    },
    card: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
      boxShadow: 'none',
    },
    navbar: {
      backgroundColor: 'rgba(0, 33, 71, 0.04)',
      borderRight: tokens.frameBorder,
    },
    navbarButton: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.6)',
    },
    navbarButtonIcon: {
      color: 'rgba(0, 33, 71, 0.4)',
    },
    pageScrollBox: {
      backgroundColor: PAPER,
    },
    profileSectionTitle: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelSection.size,
      letterSpacing: tokens.type.labelSection.letterSpacing,
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.6)',
    },
    profileSectionTitleText: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelSection.size,
      letterSpacing: tokens.type.labelSection.letterSpacing,
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.6)',
    },
    formFieldLabel: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.6)',
    },
    formFieldInput: {
      fontFamily: tokens.font.body,
      fontSize: tokens.type.bodySm.size,
      color: OXford,
      backgroundColor: 'transparent',
      border: 'none',
      borderBottom: '1px solid rgba(0, 33, 71, 0.25)',
      borderRadius: 0,
    },
    formButtonPrimary: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      backgroundColor: OXford,
      color: IVORY,
      borderRadius: 0,
    },
    formResendCodeLink: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      color: 'rgba(0, 33, 71, 0.6)',
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
      color: OXford,
    },
    userButtonPopoverActionButton: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.labelTab.size,
      letterSpacing: tokens.type.labelTab.letterSpacing,
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.8)',
    },
    userButtonPopoverActionButtonIcon: {
      color: 'rgba(0, 33, 71, 0.4)',
    },
  },
};
