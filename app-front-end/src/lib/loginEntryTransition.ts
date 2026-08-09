export const LOGIN_ENTRY_SESSION_KEY = 'aethria_just_logged_in';

export type LoginEntryTransition = {
  contentExitMs: number;
  appRevealMs: number;
  navigateDelayMs: number;
};

export function getLoginEntryTransition(reduceMotion: boolean): LoginEntryTransition {
  return reduceMotion
    ? { contentExitMs: 0, appRevealMs: 80, navigateDelayMs: 0 }
    : { contentExitMs: 180, appRevealMs: 300, navigateDelayMs: 120 };
}
