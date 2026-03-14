/**
 * Clerk component appearance — matches Aethria design tokens.
 * Palette: oxford #002147, paper #F2F0EA, ivory #fcfcfc.
 * Typography: Inter (body, names), Space Mono (labels/actions); no rounded corners.
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
    colorShadow: 'rgba(0, 33, 71, 0.12)',
    fontFamily: tokens.font.body,
    fontFamilyButtons: tokens.font.mono,
    borderRadius: '0',
  },
};

/** UserProfile modal (Manage account panel) — ensure panel and backdrop are visible */
export const userProfileAppearance = {
  variables: {
    ...clerkAppearance.variables,
    colorModalBackdrop: 'rgba(0, 33, 71, 0.4)',
  },
  elements: {
    modalContent: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
      boxShadow: '0 8px 32px rgba(0, 33, 71, 0.2)',
    },
    card: {
      backgroundColor: PAPER,
      border: tokens.frameBorder,
      borderRadius: 0,
    },
    navbar: {
      backgroundColor: 'rgba(0, 33, 71, 0.04)',
      borderRight: tokens.frameBorder,
    },
    pageScrollBox: {
      backgroundColor: PAPER,
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
      boxShadow: '0 1px 0 0 rgba(255,255,255,0.06)',
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
      boxShadow: '0 4px 24px rgba(0, 33, 71, 0.12)',
    },
    userButtonPopoverMain: {
      fontFamily: tokens.font.body,
      fontSize: tokens.type.intro,
      letterSpacing: '0.08em',
      color: OXford,
    },
    userButtonPopoverActionButton: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.type.metadataLabel,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: 'rgba(0, 33, 71, 0.8)',
    },
    userButtonPopoverActionButtonIcon: {
      color: 'rgba(0, 33, 71, 0.5)',
    },
  },
};
