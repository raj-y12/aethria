export const LOGIN_ENTRY_SESSION_KEY = 'aethria_just_logged_in';

export type LoginEntryTransition = {
  contentExitMs: number;
  overlayMs: number;
  navigateDelayMs: number;
};

export function getLoginEntryTransition(reduceMotion: boolean): LoginEntryTransition {
  return reduceMotion
    ? { contentExitMs: 0, overlayMs: 80, navigateDelayMs: 0 }
    : { contentExitMs: 260, overlayMs: 520, navigateDelayMs: 420 };
}
