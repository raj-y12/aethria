export const LOGIN_ENTRY_SESSION_KEY = 'aethria_just_logged_in';

export type LoginEntryTransition = {
  contentExitMs: number;
  navigateDelayMs: number;
};

export function getLoginEntryTransition(reduceMotion: boolean): LoginEntryTransition {
  return reduceMotion
    ? { contentExitMs: 0, navigateDelayMs: 0 }
    : { contentExitMs: 180, navigateDelayMs: 180 };
}

