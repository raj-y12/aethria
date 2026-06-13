import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence, animate } from 'framer-motion';
import { useNavigate } from 'react-router';
import { useSignIn, useUser, useClerk } from '@clerk/react-router';
import { usePrefersReducedMotion } from '../hooks';
import AuthInstitutionalFooter from './AuthInstitutionalFooter';
import CountUp from './CountUp';
import { fetchActivitySummaryWithToken, type ActivitySummary } from '../api/activity';
import { getLoginEntryTransition, LOGIN_ENTRY_SESSION_KEY } from '../lib/loginEntryTransition';

const EASE = [0.16, 1, 0.3, 1] as const;

function friendlyIdentifier(id: string): string {
  const t = id.trim();
  if (!t) return 'there';
  const at = t.indexOf('@');
  if (at > 0) return t.slice(0, at);
  return t.length > 36 ? `${t.slice(0, 33)}…` : t;
}

const STATS_CONFIG = (s: ActivitySummary) => [
  { label: 'Discovered', value: s.found, accent: false },
  { label: 'Evaluated', value: s.reviewed, accent: false },
  { label: 'Agent-decided', value: s.agent_decided ?? s.decided, accent: false },
  { label: 'Escalated', value: s.escalations, accent: true },
];

/** Input with an animated underline that expands from center on focus. */
const AnimatedInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { focused: boolean }
>(({ focused, className, ...props }, ref) => (
  <div className="relative">
    <input ref={ref} className={className} {...props} />
    <div className="absolute bottom-0 left-0 right-0 h-px bg-oxford/10" />
    <motion.div
      className="absolute bottom-0 left-1/2 h-px -translate-x-1/2 bg-oxford/40"
      animate={{ width: focused ? '100%' : '0%' }}
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
            const summary = await fetchActivitySummaryWithToken(token);
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
  }, [loading, phase, username, password, signIn, navigate, isSignedIn, clerk]);

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

  const stats = activity ? STATS_CONFIG(activity) : null;
  const enterDelay = stats ? 0.22 + stats.length * 0.07 + 0.1 : 0.2;
  const entryTransition = getLoginEntryTransition(reduceMotion);

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper">
      <div
        className="relative z-10 flex flex-1 flex-col items-center justify-center overflow-hidden"
        style={{ padding: 'clamp(24px, 5vw, 56px)' }}
      >
      <motion.div
        className="w-full max-w-[40rem] flex flex-col items-center"
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
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: '11px',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'rgba(var(--color-oxford-rgb), 0.55)',
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
                Agents continued working. Here is what happened.
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="brand-header"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.25, ease: EASE } }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.3 }}
              className="flex flex-col items-center mb-phi-9"
            >
              <h1 className="font-wordmark text-center text-[clamp(48px,8vw,80px)] font-medium text-oxford leading-[0.9] m-0 tracking-normal">
                Aethria<span className="wordmark-dot">.</span>
              </h1>
              <p className="type-meta uppercase tracking-[0.14em] text-oxford/35 mt-phi-4">
                Deal flow operating system
              </p>
            </motion.div>
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
              {!activityLoading && stats && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'flex-start',
                    justifyContent: 'center',
                    gap: 'clamp(48px, 8vw, 120px)',
                    marginBottom: '64px',
                    flexWrap: 'wrap',
                  }}
                >
                  {stats.map((stat, i) => (
                    <motion.div
                      key={stat.label}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.45, ease: EASE, delay: 0.22 + i * 0.07 }}
                      style={{ textAlign: 'center' }}
                    >
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 'clamp(52px, 10vw, 96px)',
                          fontWeight: 400,
                          lineHeight: 1,
                          color: stat.accent ? 'var(--color-accent)' : 'var(--color-oxford)',
                          letterSpacing: '-0.03em',
                          // Reserve the final digit width up front — the count-up
                          // otherwise reflows the row every frame as digits grow.
                          minWidth: `${stat.value.toLocaleString().length}ch`,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        <CountUp to={stat.value} delay={0.22 + i * 0.07} reduceMotion={reduceMotion} />
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: '13px',
                          color: 'rgba(var(--color-oxford-rgb), 0.6)',
                          marginTop: '6px',
                          letterSpacing: '0.01em',
                        }}
                      >
                        {stat.label}
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* No activity */}
              {!activityLoading && !stats && (
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

              {/* CTA */}
              {!activityLoading && (
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
                      className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                      aria-hidden
                    >
                      {' →'}
                    </span>
                  </span>
                </motion.button>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="form-view"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12, transition: { duration: 0.28, ease: EASE } }}
              transition={{ duration: 0.6, ease: EASE, delay: 0.5 }}
              className="w-full max-w-[360px]"
            >
              <form
                onSubmit={(e) => { e.preventDefault(); void handleSubmit(); }}
                className="flex flex-col"
                noValidate
              >
                {/* Inputs — shake ref wraps both so both move on error */}
                <div ref={formShakeRef} className="flex flex-col gap-phi-5 mb-phi-8">
                  <div className="flex flex-col">
                    <label htmlFor="login-identifier" className="sr-only">
                      Email or username
                    </label>
                    <AnimatedInput
                      id="login-identifier"
                      type="text"
                      autoComplete="username"
                      placeholder="Email or username"
                      value={username}
                      focused={usernameFocused}
                      onChange={(e) => setUsername(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e as React.KeyboardEvent, 'username')}
                      onFocus={() => setUsernameFocused(true)}
                      onBlur={() => setUsernameFocused(false)}
                      aria-describedby={error ? 'login-error' : undefined}
                      className="w-full bg-transparent border-0 py-phi-3 font-sans text-sm text-oxford outline-none placeholder:text-oxford/35 tracking-0"
                    />
                  </div>
                  <div className="flex flex-col">
                    <label htmlFor="login-password" className="sr-only">
                      Password
                    </label>
                    <AnimatedInput
                      ref={passwordRef}
                      id="login-password"
                      type="password"
                      autoComplete="current-password"
                      placeholder="Password"
                      value={password}
                      focused={passwordFocused}
                      onChange={(e) => setPassword(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e as React.KeyboardEvent, 'password')}
                      onFocus={() => setPasswordFocused(true)}
                      onBlur={() => setPasswordFocused(false)}
                      aria-describedby={error ? 'login-error' : undefined}
                      className="w-full bg-transparent border-0 py-phi-3 font-sans text-sm text-oxford outline-none placeholder:text-oxford/35 tracking-0"
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
                      className="type-meta text-[11px] text-escalation text-center mb-phi-6 tracking-[0.06em]"
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
                          className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                          aria-hidden
                        >
                          {' →'}
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
      </div>
    </div>
  );
}
