import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence, animate } from 'framer-motion';
import { useNavigate } from 'react-router';
import { useSignIn, useUser, useClerk } from '@clerk/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { usePrefersReducedMotion } from '../hooks';
import AuthInstitutionalFooter from './AuthInstitutionalFooter';
import ActivityStatsRow, { activityStatsFromSummary } from './ActivityStatsRow';
import {
  fetchActivitySummaryWithToken,
  markActivitySeenWithToken,
  pingBackendWarmup,
  type ActivitySummary,
} from '../api/activity';
import { getLoginEntryTransition, LOGIN_ENTRY_SESSION_KEY } from '../lib/loginEntryTransition';
import { fetchStartupsWithToken } from '../api/startups';
import { bureauTimes, editionNo } from '../lib/clocks';

const EASE = [0.16, 1, 0.3, 1] as const;

function friendlyIdentifier(id: string): string {
  const t = id.trim();
  if (!t) return 'there';
  const at = t.indexOf('@');
  if (at > 0) return t.slice(0, at);
  return t.length > 36 ? `${t.slice(0, 33)}…` : t;
}

/** Input with an animated underline that expands from center on focus. */
const AnimatedInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { focused: boolean }
>(({ focused, className, ...props }, ref) => (
  <div className="relative">
    <input ref={ref} className={className} {...props} />
    <div className="absolute bottom-0 left-0 right-0 h-px bg-oxford/10" />
    <motion.div
      className="absolute bottom-0 left-0 right-0 h-px origin-center bg-oxford/40"
      initial={{ scaleX: 0 }}
      animate={{ scaleX: focused ? 1 : 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
    />
  </div>
));

type Phase = 'form' | 'welcome';

export default function LoginPage() {
  const reduceMotion = usePrefersReducedMotion();
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useUser();
  const { signIn } = useSignIn();
  const clerk = useClerk();
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<Phase>('form');
  const [welcomeName, setWelcomeName] = useState('');
  const [activity, setActivity] = useState<ActivitySummary | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [entering, setEntering] = useState(false);
  const [usernameFocused, setUsernameFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);

  const passwordRef = useRef<HTMLInputElement>(null);
  const hasRedirectedRef = useRef(false);
  const formShakeRef = useRef<HTMLDivElement>(null);
  const enterTimeoutRef = useRef<number | null>(null);
  const activityTokenRef = useRef<string | null>(null);

  // Wake a cold backend while the user types credentials, so the first
  // authenticated call (the welcome screen's activity summary) lands warm.
  useEffect(() => {
    pingBackendWarmup();
  }, []);

  // Quiet corner furniture (lg+ only): bureau clocks bottom-left, edition
  // number bottom-right — mirrors the marketing gallery frame. Ticks once a
  // second; reduced motion renders a single static read.
  const [bureau, setBureau] = useState<{ label: string; time: string }[] | null>(null);
  const [edition] = useState(editionNo());
  useEffect(() => {
    setBureau(bureauTimes());
    if (reduceMotion) return;
    const id = window.setInterval(() => setBureau(bureauTimes()), 1000);
    return () => window.clearInterval(id);
  }, [reduceMotion]);

  useEffect(() => {
    return () => {
      if (enterTimeoutRef.current !== null) {
        window.clearTimeout(enterTimeoutRef.current);
      }
    };
  }, []);

  // Auto-redirect already signed-in users
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    if (phase === 'welcome') return;
    if (hasRedirectedRef.current) return;
    hasRedirectedRef.current = true;
    navigate('/v1', { replace: true });
  }, [isLoaded, isSignedIn, navigate, phase]);

  // Shake the input fields when an error is set
  useEffect(() => {
    if (!error || reduceMotion || !formShakeRef.current) return;
    animate(
      formShakeRef.current,
      { x: [0, -7, 7, -5, 5, -2, 2, 0] },
      { duration: 0.38, ease: 'easeInOut' }
    );
  }, [error, reduceMotion]);

  const handleEnterSystem = useCallback(() => {
    if (entering) return;
    const transition = getLoginEntryTransition(reduceMotion);
    sessionStorage.setItem(LOGIN_ENTRY_SESSION_KEY, '1');
    const activityToken = activityTokenRef.current;
    if (activityToken) void markActivitySeenWithToken(activityToken).catch(() => {});
    setEntering(true);
    enterTimeoutRef.current = window.setTimeout(() => {
      navigate('/v1', { replace: true });
    }, transition.navigateDelayMs);
  }, [entering, navigate, reduceMotion]);

  const handleSubmit = useCallback(async () => {
    if (loading || phase === 'welcome') return;
    setError(null);
    setLoading(true);

    const trimmedUsername = username.trim();
    if (!trimmedUsername || !password) {
      setError('Enter both username and password to continue.');
      setLoading(false);
      return;
    }
    if (!signIn) {
      setError('Sign-in is not ready. Refresh the page and try again.');
      setLoading(false);
      return;
    }
    if (isSignedIn) {
      navigate('/v1', { replace: true });
      return;
    }

    try {
      const result = await signIn.password({ identifier: trimmedUsername, password });

      if (result.error) {
        const msg = (result.error as { message?: string }).message ?? '';
        if (msg.toLowerCase().includes('already signed in')) {
          navigate('/v1', { replace: true });
          return;
        }
        setError(
          typeof (result.error as { message?: string }).message === 'string'
            ? String((result.error as { message?: string }).message)
            : 'Invalid username or password.'
        );
        setLoading(false);
        return;
      }

      if (signIn.status === 'complete') {
        const name = friendlyIdentifier(trimmedUsername);
        setWelcomeName(name);
        setPhase('welcome');
        setActivityLoading(true);

        try {
          type ClerkSignInInternal = {
            finalize?: () => Promise<unknown>;
            createdSessionId?: string;
          };
          const signInInternal = signIn as unknown as ClerkSignInInternal;
          if (typeof signInInternal.finalize === 'function') {
            await signInInternal.finalize();
          } else if (clerk.setActive && signInInternal.createdSessionId) {
            await clerk.setActive({ session: signInInternal.createdSessionId });
          }
          const token = await clerk.session?.getToken();
          if (token) {
            activityTokenRef.current = token;
            // Use the authenticated welcome beat to seed the primary app query.
            // Register the preload with TanStack Query so navigation subscribes
            // to the same in-flight request instead of issuing a duplicate GET.
            const startupPreload = queryClient.fetchQuery({
              queryKey: ['startups', 'list'],
              queryFn: async () => {
                const startups = await fetchStartupsWithToken(token);
                if (!startups) throw new Error('startup preload unavailable');
                return startups;
              },
              staleTime: 90_000,
            }).catch(() => null);
            const [summary] = await Promise.all([
              fetchActivitySummaryWithToken(token),
              startupPreload,
            ]);
            if (summary) setActivity(summary);
          }
        } catch {
          /* activity is optional */
        } finally {
          setActivityLoading(false);
        }
        return;
      }

      setError('Sign-in could not be completed. Please try again.');
      setLoading(false);
    } catch (err: unknown) {
      const e = err as { errors?: { message?: string }[]; message?: string };
      const msg =
        Array.isArray(e?.errors) && e.errors[0]?.message
          ? String(e.errors[0].message)
          : e?.message
            ? String(e.message)
            : '';
      if (
        msg.toLowerCase().includes('already signed in') ||
        msg.toLowerCase().includes('session_exists')
      ) {
        navigate('/v1', { replace: true });
        return;
      }
      setError(
        Array.isArray(e?.errors) && e.errors[0]?.message
          ? String(e.errors[0].message)
          : e?.message
            ? String(e.message)
            : 'Something went wrong. Please try again.'
      );
      setPassword('');
      passwordRef.current?.focus();
      setLoading(false);
    }
  }, [loading, phase, username, password, signIn, navigate, isSignedIn, clerk, queryClient]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, field: 'username' | 'password') => {
      if (e.key === 'Enter') {
        if (field === 'username') passwordRef.current?.focus();
        else void handleSubmit();
      }
    },
    [handleSubmit]
  );

  if (!isLoaded) return null;

  const stats = activity ? activityStatsFromSummary(activity) : [];
  const hasStats = stats.length > 0;
  const enterDelay = hasStats ? 0.22 + stats.length * 0.07 + 0.1 : 0.2;
  const entryTransition = getLoginEntryTransition(reduceMotion);

  const dateline = new Date()
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    .toUpperCase();

  return (
    <div className="paper-dot-grid flex min-h-[100dvh] flex-col overflow-hidden bg-paper">
      <div
        className="relative z-10 flex flex-1 flex-col items-center justify-center overflow-hidden"
        style={{ padding: 'clamp(28px, 6vw, 72px)' }}
      >
      <motion.div
        className="w-full max-w-[42rem] flex flex-col items-center"
        animate={
          entering
            ? reduceMotion
              ? { opacity: 0 }
              : { opacity: 0, y: -12 }
            : { opacity: 1, y: 0 }
        }
        transition={{
          duration: entryTransition.contentExitMs / 1000,
          ease: EASE,
        }}
      >

        {/* Eyebrow */}
        <AnimatePresence mode="wait">
          {phase === 'welcome' ? (
            <motion.p
              key="eyebrow-report"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.2, ease: EASE } }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.05 }}
              className="type-label-section"
              style={{
                marginBottom: '16px',
              }}
            >
              System Report
            </motion.p>
          ) : null}
        </AnimatePresence>

        {/* Heading */}
        <AnimatePresence mode="wait">
          {phase === 'welcome' ? (
            <motion.div
              key="welcome-header"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.25, ease: EASE } }}
              transition={{ duration: 0.5, ease: EASE }}
              className="flex flex-col items-center"
            >
              <h1
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: 'clamp(28px, 3.5vw, 44px)',
                  fontWeight: 500,
                  color: 'var(--color-oxford)',
                  lineHeight: 1.1,
                  margin: 0,
                  textAlign: 'center',
                }}
              >
                Welcome back, {welcomeName}.
              </h1>
              <p
                style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: '14px',
                  color: 'rgba(var(--color-oxford-rgb), 0.6)',
                  marginTop: '12px',
                  marginBottom: '55px',
                  textAlign: 'center',
                }}
              >
                {activityLoading || hasStats
                  ? 'Agents continued working. Here is what happened.'
                  : 'Your workspace is current.'}
              </p>
            </motion.div>
          ) : (
            <div key="brand-header" className="flex w-full flex-col items-center">
              {/* Settle-in stagger: kicker, then the mark+subtitle, then the
                  fields below settle in turn (see form-view). Resting state
                  is fully visible without JS/on reduced motion. */}
              <motion.p
                initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.2, ease: EASE } }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.4, ease: EASE, delay: 0.05 }}
                className="type-label-section m-0 mb-phi-5 text-center tabular-nums"
              >
                {dateline}
              </motion.p>
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8, transition: { duration: 0.25, ease: EASE } }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.45, ease: EASE, delay: 0.18 }}
                className="flex w-full flex-col items-center mb-phi-8"
              >
                <h1 className="font-wordmark text-center text-[clamp(56px,9vw,96px)] font-medium text-oxford leading-[0.9] m-0 tracking-[-0.02em]">
                  Aethria<span className="wordmark-dot">.</span>
                </h1>
                <p className="type-label-section mt-phi-4">
                  Deal flow operating system
                </p>
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        {/* Body */}
        <AnimatePresence mode="wait">
          {phase === 'welcome' ? (
            <motion.div
              key="activity-view"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease: EASE, delay: 0.08 }}
              className="w-full flex flex-col items-center"
            >
              {/* Loading pulse */}
              {activityLoading && (
                <motion.p
                  animate={reduceMotion ? { opacity: 1 } : { opacity: [0.35, 0.8, 0.35] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: '14px',
                    color: 'rgba(var(--color-oxford-rgb), 0.4)',
                    marginBottom: '64px',
                    textAlign: 'center',
                  }}
                >
                  Preparing workspace...
                </motion.p>
              )}

              {/* Stats — numbers count up on reveal */}
              {!activityLoading && hasStats && (
                <div style={{ marginBottom: '64px' }}>
                  <ActivityStatsRow stats={stats} reduceMotion={reduceMotion} />
                </div>
              )}

              {/* No activity */}
              {!activityLoading && !hasStats && (
                <p
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: '14px',
                    color: 'rgba(var(--color-oxford-rgb), 0.6)',
                    marginBottom: '64px',
                    textAlign: 'center',
                  }}
                >
                  Everything is current.
                </p>
              )}

              {/* The optional activity request must never gate entry. */}
              <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.4, ease: EASE, delay: enterDelay }}
                  whileTap={reduceMotion ? {} : { scale: 0.97 }}
                  onClick={handleEnterSystem}
                  disabled={entering}
                  className="group btn-aethria-solid"
                  style={{ padding: '0 72px' }}
                >
                  <span className="flex items-center justify-center">
                    <span>Enter Aethria</span>
                    <span
                      className="inline-block w-6 shrink-0 overflow-hidden whitespace-nowrap"
                      aria-hidden
                    >
                      <span className="inline-block -translate-x-2 opacity-0 transition-[transform,opacity] duration-[250ms] ease group-hover:translate-x-0 group-hover:opacity-100">{' →'}</span>
                    </span>
                  </span>
              </motion.button>
            </motion.div>
          ) : (
            <motion.div
              key="form-view"
              initial={reduceMotion ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12, transition: { duration: 0.28, ease: EASE } }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.5, ease: EASE, delay: 0.32 }}
              className="w-full max-w-[420px]"
            >
              <form
                onSubmit={(e) => { e.preventDefault(); void handleSubmit(); }}
                className="flex flex-col"
                noValidate
              >
                {/* Inputs live in a hairline band — the same construction as the
                    home page's doors band. No boxes; the rules do the framing. */}
                <div
                  ref={formShakeRef}
                  className="mb-phi-7 flex w-full flex-col gap-phi-6 border-y border-oxford/[0.12] py-phi-6"
                >
                  <div className="flex flex-col">
                    <label
                      htmlFor="login-identifier"
                      className="type-label-section mb-phi-2"
                    >
                      Email or username
                    </label>
                    <AnimatedInput
                      id="login-identifier"
                      type="text"
                      autoComplete="username"
                      value={username}
                      focused={usernameFocused}
                      onChange={(e) => setUsername(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e as React.KeyboardEvent, 'username')}
                      onFocus={() => setUsernameFocused(true)}
                      onBlur={() => setUsernameFocused(false)}
                      aria-describedby={error ? 'login-error' : undefined}
                      className="w-full bg-transparent border-0 py-phi-3 font-sans text-sm text-oxford outline-none placeholder:text-oxford/60 tracking-0"
                    />
                  </div>
                  <div className="flex flex-col">
                    <label
                      htmlFor="login-password"
                      className="type-label-section mb-phi-2"
                    >
                      Password
                    </label>
                    <AnimatedInput
                      ref={passwordRef}
                      id="login-password"
                      type="password"
                      autoComplete="current-password"
                      value={password}
                      focused={passwordFocused}
                      onChange={(e) => setPassword(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e as React.KeyboardEvent, 'password')}
                      onFocus={() => setPasswordFocused(true)}
                      onBlur={() => setPasswordFocused(false)}
                      aria-describedby={error ? 'login-error' : undefined}
                      className="w-full bg-transparent border-0 py-phi-3 font-sans text-sm text-oxford outline-none placeholder:text-oxford/60 tracking-0"
                    />
                  </div>
                </div>

                {/* Error — slides down into view, keyed so re-triggering replays */}
                <AnimatePresence>
                  {error && (
                    <motion.p
                      key={error}
                      id="login-error"
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2, ease: EASE }}
                      className="type-meta mb-phi-6 text-center text-escalation"
                    >
                      {error}
                    </motion.p>
                  )}
                </AnimatePresence>

                {/* Submit — press scale + breathing pulse when loading */}
                <motion.button
                  type="submit"
                  disabled={loading}
                  whileTap={reduceMotion || loading ? {} : { scale: 0.97 }}
                  transition={{ duration: 0.1 }}
                  className="group w-full btn-aethria-solid disabled:opacity-40"
                >
                  <span className="flex items-center justify-center">
                    {loading ? (
                      <motion.span
                        animate={reduceMotion ? {} : { opacity: [1, 0.4, 1] }}
                        transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
                      >
                        Authenticating...
                      </motion.span>
                    ) : (
                      <>
                        <span>Enter Aethria</span>
                        <span
                          className="inline-block w-6 shrink-0 overflow-hidden whitespace-nowrap"
                          aria-hidden
                        >
                          <span className="inline-block -translate-x-2 opacity-0 transition-[transform,opacity] duration-[250ms] ease group-hover:translate-x-0 group-hover:opacity-100">{' →'}</span>
                        </span>
                      </>
                    )}
                  </span>
                </motion.button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: entering ? 0 : 1 }}
        transition={{ duration: entering ? entryTransition.contentExitMs / 1000 : 1, delay: entering ? 0 : 1 }}
        className="fixed bottom-0 left-0 z-20 w-full p-phi-6 flex justify-center pointer-events-none"
      >
        <AuthInstitutionalFooter />
      </motion.footer>

      {/* Corner marginal furniture (lg+ only) — quiet bureau clocks + edition
          number, mirroring the marketing gallery frame's bl/br corners. */}
      <div
        className="pointer-events-none fixed bottom-8 left-8 z-20 hidden lg:block plate-num"
        aria-hidden
      >
        {(bureau ?? [{ label: 'London', time: '—:—:—' }, { label: 'San Francisco', time: '—:—:—' }]).map(
          ({ label, time }) => (
            <div key={label}>{time} &nbsp; {label}</div>
          )
        )}
      </div>
      <div
        className="pointer-events-none fixed bottom-8 right-8 z-20 hidden lg:block plate-num"
        aria-hidden
      >
        No. {edition}
      </div>
      </div>
    </div>
  );
}
